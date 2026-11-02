"""Egyptian Voice Sender - Streamlit UI.

Generate Egyptian Arabic voice notes (Groq -> OpenAI -> Azure -> Windows fallback)
and send them through the official WhatsApp Cloud API only.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src import config
from src.database import Database
from src.text_refiner import ENGINE_OLLAMA, ENGINE_ORDER, RefineError, default_engine, engine_ready, ollama_available, refine_to_egyptian, write_message
from src.tts_service import (
    GROQ_ARABIC_VOICES,
    PROVIDER_GROQ,
    PROVIDER_ORDER,
    PROVIDER_WINDOWS,
    TTSGenerationError,
    TTSSetupError,
    default_provider,
    generate_speech,
    provider_statuses,
)
from src.validators import is_egyptian_mobile, normalize_phone
from src.whatsapp_service import (
    WhatsAppSendError,
    WhatsAppSetupError,
    check_sender,
    manual_chat_link,
    send_audio,
    send_text,
)

st.set_page_config(page_title="Egyptian Voice Sender", page_icon="🎙️", layout="wide")


@st.cache_resource
def get_db() -> Database:
    return Database()


db = get_db()

# --- sidebar: credential and provider readiness (never shows values) ---------------
with st.sidebar:
    st.header("Setup status")
    st.caption("Keys are read from `keys.txt` / `API keys.txt`, `.env`, or Streamlit secrets. Values are never displayed.")
    if config.LOADED_KEYS_FILE:
        st.caption(f"Keys file: `{config.LOADED_KEYS_FILE}`")
    for name, present in config.credential_status().items():
        st.write(("✅ " if present else "❌ ") + f"`{name}`")
    st.divider()
    st.subheader("AI text engine")
    engine_options = [e for e in ENGINE_ORDER if e != ENGINE_OLLAMA or ollama_available()]
    preferred = default_engine()
    text_engine = st.radio(
        "Writes and refines the message",
        engine_options,
        index=engine_options.index(preferred) if preferred in engine_options else 0,
        key="text_engine",
        help="Groq is the default. Claude is available when ANTHROPIC_API_KEY is set.",
    )
    ready, message = engine_ready(text_engine)
    st.write(("✅ " if ready else "⚠️ ") + message)
    st.divider()
    st.subheader("Voice providers")
    for status in provider_statuses():
        st.write(("✅ " if status.ready else "⚠️ ") + f"**{status.name}** — {status.message}")
    st.divider()
    st.caption(config.AI_DISCLOSURE)

st.title("🎙️ Egyptian Voice Sender")
st.info(f"Disclosure: every file produced here is labelled “{config.AI_DISCLOSURE}”", icon="ℹ️")

tab_generate, tab_contacts, tab_senders, tab_log = st.tabs(
    ["Generate & Send", "Contacts", "Authorized Sender Manager", "Send log"]
)

# =============================================================================
# Generate & Send
# =============================================================================
with tab_generate:
    col_text, col_opts = st.columns([3, 2])

    with col_text:
        with st.expander(f"Write with {text_engine} from a short brief", expanded=not st.session_state.get("message_text")):
            brief = st.text_area(
                "What should the voice note say? (any language)",
                height=90,
                key="brief_text",
                placeholder="مثال: فكّر أحمد إن الاجتماع بكرة الساعة 5 ولازم يجيب العقد معاه",
            )
            if st.button(f"Write with {text_engine}", disabled=not (brief.strip() and ready)):
                with st.spinner(f"{text_engine} is writing..."):
                    try:
                        drafted, engine_used = write_message(brief, text_engine)
                        st.session_state["message_text"] = drafted
                        st.session_state.pop("refined_text", None)
                        st.rerun()
                    except RefineError as exc:
                        st.error(str(exc))

        text = st.text_area(
            "Message text (Egyptian Arabic)",
            height=180,
            key="message_text",
            placeholder="اكتب الرسالة هنا...",
        )
        if st.button(f"Refine into Egyptian dialect with {text_engine}", disabled=not (text.strip() and ready)):
            with st.spinner(f"{text_engine} is refining..."):
                try:
                    refined, engine_used = refine_to_egyptian(text, text_engine)
                    st.session_state["refined_text"] = refined
                    st.session_state["refined_engine"] = engine_used
                except RefineError as exc:
                    st.error(str(exc))
        if st.session_state.get("refined_text"):
            st.text_area(
                f"Refined by {st.session_state.get('refined_engine', '')}",
                value=st.session_state["refined_text"], height=120, key="refined_view",
            )
            if st.button("Use refined text"):
                st.session_state["message_text"] = st.session_state["refined_text"]
                st.session_state.pop("refined_text", None)
                st.rerun()

    with col_opts:
        provider = st.selectbox(
            "Voice provider",
            PROVIDER_ORDER,
            index=PROVIDER_ORDER.index(default_provider()),
            help="Order of preference: Groq, OpenAI, Azure, then the Windows fallback.",
        )
        status = next(s for s in provider_statuses() if s.name == provider)
        if not status.ready:
            st.warning(status.message)
        if provider == PROVIDER_WINDOWS:
            st.warning(status.warning)
        if provider == PROVIDER_GROQ:
            voice = st.selectbox(
                "Groq voice",
                GROQ_ARABIC_VOICES,
                index=GROQ_ARABIC_VOICES.index(config.groq_tts_voice())
                if config.groq_tts_voice() in GROQ_ARABIC_VOICES
                else 0,
            )
            st.caption("Groq Orpheus Arabic is a Saudi-dialect model; write the text in Egyptian dialect.")
        else:
            voice = st.text_input("Voice (blank = provider default)", value="")

        if st.button("Generate Voice", type="primary", disabled=not text.strip()):
            with st.spinner(f"Generating with {provider}..."):
                try:
                    mp3 = generate_speech(text, provider, voice or None)
                    st.session_state["last_audio"] = str(mp3)
                    st.success(f"Saved {mp3.name} in generated_audio/")
                except TTSSetupError as exc:
                    st.error(f"Setup problem: {exc}")
                except (TTSGenerationError, ValueError) as exc:
                    st.error(str(exc))

    last_audio = st.session_state.get("last_audio")
    if last_audio and Path(last_audio).exists():
        st.subheader("Preview")
        audio_bytes = Path(last_audio).read_bytes()
        st.audio(audio_bytes, format="audio/mpeg")
        st.download_button("Download MP3", audio_bytes, file_name=Path(last_audio).name, mime="audio/mpeg")
        st.caption(config.AI_DISCLOSURE)

    st.divider()
    st.subheader("Send via WhatsApp Cloud API")
    st.caption(
        "Sends only through an authorized Meta phone_number_id. "
        "A plain phone number is never used as the sender."
    )

    senders = db.list_authorized_senders()
    contacts = db.list_contacts()
    col_from, col_to = st.columns(2)

    with col_from:
        if senders:
            sender_label = st.selectbox(
                "Authorized sender",
                [f"{s['display_name']} — {s['normalized_e164']} (id {s['phone_number_id']})" for s in senders],
            )
            sender = senders[[f"{s['display_name']} — {s['normalized_e164']} (id {s['phone_number_id']})" for s in senders].index(sender_label)]
        else:
            sender = None
            st.warning("No authorized sender saved. Add one in the Authorized Sender Manager tab.")

    with col_to:
        locked = config.locked_recipient_number()
        if locked:
            try:
                locked_norm = normalize_phone(locked)
                recipient_input = locked_norm.normalized_e164
                st.text_input("Recipient (locked by LOCKED_RECIPIENT_NUMBER)", value=recipient_input, disabled=True)
            except ValueError as exc:
                recipient_input = ""
                st.error(f"LOCKED_RECIPIENT_NUMBER is invalid: {exc}")
        else:
            options = ["Type a number"] + [f"{c['name']} — {c['normalized_e164']}" for c in contacts]
            choice = st.selectbox("Recipient", options)
            if choice == "Type a number":
                recipient_input = st.text_input("Recipient number", placeholder="01123040202 or +201123040202")
            else:
                recipient_input = contacts[options.index(choice) - 1]["normalized_e164"]

        recipient_norm = None
        if recipient_input:
            try:
                recipient_norm = normalize_phone(recipient_input)
                tag = "Egyptian mobile" if is_egyptian_mobile(recipient_norm.normalized_e164) else "international"
                st.caption(f"Will send to **{recipient_norm.normalized_e164}** ({tag}).")
            except ValueError as exc:
                st.error(str(exc))

    can_send = bool(sender and recipient_norm and last_audio and Path(last_audio).exists())
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        if st.button("Send audio via Cloud API", type="primary", disabled=not can_send):
            with st.spinner("Uploading and sending..."):
                try:
                    result = send_audio(sender["phone_number_id"], recipient_norm.normalized_e164, Path(last_audio))
                    db.log_send(result.recipient_e164, sender["phone_number_id"], last_audio, "sent", result.message_id)
                    st.success(f"Sent. Message id: {result.message_id}")
                except (WhatsAppSetupError, WhatsAppSendError, ValueError) as exc:
                    db.log_send(recipient_norm.normalized_e164, sender["phone_number_id"], last_audio, "failed", error=str(exc))
                    st.error(str(exc))

    with col_b:
        if st.button("Send test text", disabled=not (sender and recipient_norm)):
            try:
                mid = send_text(sender["phone_number_id"], recipient_norm.normalized_e164, f"Test from Egyptian Voice Sender. {config.AI_DISCLOSURE}")
                db.log_send(recipient_norm.normalized_e164, sender["phone_number_id"], None, "sent-text", mid)
                st.success(f"Text sent. Message id: {mid}")
            except (WhatsAppSetupError, WhatsAppSendError, ValueError) as exc:
                st.error(str(exc))

    with col_c:
        if recipient_norm and last_audio:
            st.link_button("Manual send: open chat in WhatsApp", manual_chat_link(recipient_norm.normalized_e164))
            st.caption("Then attach this file yourself:")
            st.code(last_audio, language="text")

# =============================================================================
# Contacts
# =============================================================================
with tab_contacts:
    st.subheader("Add contact")
    with st.form("add_contact", clear_on_submit=True):
        c_name = st.text_input("Name")
        c_phone = st.text_input("Phone", placeholder="01123040202 → stored as +201123040202")
        if st.form_submit_button("Save contact"):
            try:
                saved = db.add_contact(c_name, c_phone)
                st.success(f"Saved {saved['name']}: {saved['original_input']} → {saved['normalized_e164']}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    contacts = db.list_contacts()
    if contacts:
        st.dataframe(
            [{k: c[k] for k in ("id", "name", "original_input", "normalized_e164", "created_at")} for c in contacts],
            use_container_width=True,
            hide_index=True,
        )
        to_delete = st.selectbox("Delete contact", ["—"] + [f"{c['id']}: {c['name']} ({c['normalized_e164']})" for c in contacts])
        if to_delete != "—" and st.button("Delete selected contact"):
            db.delete_contact(int(to_delete.split(":")[0]))
            st.rerun()
    else:
        st.caption("No contacts yet.")

# =============================================================================
# Authorized Sender Manager
# =============================================================================
with tab_senders:
    st.subheader("Authorized WhatsApp Business senders")
    st.caption(
        "Only numbers registered in Meta WhatsApp Manager can send. The phone_number_id "
        "is what the API uses; the business number is shown for display and validation only. "
        "An SMS-registered number can receive OTP codes but is not a WhatsApp sender by itself."
    )
    with st.form("add_sender", clear_on_submit=True):
        s_name = st.text_input("Display name")
        s_pnid = st.text_input("Meta phone_number_id (numeric)")
        s_phone = st.text_input("Business phone number", placeholder="01123040202 or +201123040202")
        s_waba = st.text_input("WABA id (optional)")
        if st.form_submit_button("Save authorized sender"):
            try:
                saved = db.add_authorized_sender(s_name, s_pnid, s_phone, s_waba)
                st.success(f"Saved {saved['display_name']}: {saved['original_input']} → {saved['normalized_e164']}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    senders = db.list_authorized_senders()
    if senders:
        st.dataframe(
            [{k: s[k] for k in ("id", "display_name", "phone_number_id", "original_input", "normalized_e164", "waba_id")} for s in senders],
            use_container_width=True,
            hide_index=True,
        )
        pick = st.selectbox("Sender", [f"{s['id']}: {s['display_name']} ({s['normalized_e164']})" for s in senders])
        sender_id = int(pick.split(":")[0])
        chosen = next(s for s in senders if s["id"] == sender_id)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Validate with Meta"):
                try:
                    info = check_sender(chosen["phone_number_id"])
                    st.success(
                        f"Meta reports {info.get('display_phone_number', '?')} "
                        f"({info.get('verified_name', 'unverified')}), quality {info.get('quality_rating', 'n/a')}."
                    )
                except (WhatsAppSetupError, WhatsAppSendError) as exc:
                    st.error(str(exc))
        with c2:
            if st.button("Delete selected sender"):
                db.delete_authorized_sender(sender_id)
                st.rerun()
    else:
        st.caption("No authorized sender saved yet.")

# =============================================================================
# Send log
# =============================================================================
with tab_log:
    log = db.list_send_log()
    if log:
        st.dataframe(log, use_container_width=True, hide_index=True)
    else:
        st.caption("No sends yet.")
