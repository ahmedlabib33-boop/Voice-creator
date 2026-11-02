"""Egyptian Voice Sender - Streamlit UI.

Three-step flow: write the message (Groq or Claude), generate the voice
(Groq -> OpenAI -> Azure -> Windows fallback), send through the official
WhatsApp Cloud API. Styling comes from src/ui_theme.py (see DESIGN_SYSTEM.md).
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src import config
from src.database import Database
from src.text_refiner import (
    ENGINE_OLLAMA,
    ENGINE_ORDER,
    RefineError,
    default_engine,
    engine_ready,
    ollama_available,
    refine_to_egyptian,
    write_message,
)
from src import elevenlabs_service
from src.tts_service import (
    GROQ_ARABIC_VOICES,
    PROVIDER_ELEVENLABS,
    PROVIDER_GROQ,
    PROVIDER_ORDER,
    PROVIDER_WINDOWS,
    TTSGenerationError,
    TTSSetupError,
    default_provider,
    generate_speech,
    provider_statuses,
)
from src.ui_theme import chips, hero, inject_theme, kpis, step
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
inject_theme()


@st.cache_resource
def get_db() -> Database:
    return Database()


db = get_db()
statuses = provider_statuses()
creds = config.credential_status()

# =============================================================================
# Sidebar: setup, engine choice, providers
# =============================================================================
with st.sidebar:
    st.markdown("### Setup")
    st.caption("Keys come from `API keys.txt` / `keys.txt`, `.env`, or Streamlit secrets. Values are never shown.")
    if config.LOADED_KEYS_FILE:
        st.caption(f"Keys file: `{config.LOADED_KEYS_FILE.name}`")
    key_labels = {
        "ELEVENLABS_API_KEY": "ElevenLabs key", "ANTHROPIC_API_KEY": "Claude key", "GROQ_API_KEY": "Groq key", "OPENAI_API_KEY": "OpenAI key",
        "AZURE_SPEECH_KEY": "Azure key", "AZURE_SPEECH_REGION": "Azure region", "WHATSAPP_ACCESS_TOKEN": "WhatsApp token",
    }
    chips([(key_labels.get(name, name), "ok" if present else "off", "") for name, present in creds.items()])

    st.markdown("### AI text engine")
    engine_options = [e for e in ENGINE_ORDER if e != ENGINE_OLLAMA or ollama_available()]
    preferred = default_engine()
    text_engine = st.radio(
        "Writes and refines the message",
        engine_options,
        index=engine_options.index(preferred) if preferred in engine_options else 0,
        key="text_engine",
        horizontal=True,
        help="Groq is the default. Claude is available when ANTHROPIC_API_KEY is set.",
    )
    engine_ok, engine_msg = engine_ready(text_engine)
    chips([(text_engine, "ok" if engine_ok else "warn", engine_msg)])

    st.markdown("### Voice providers")
    chips([(s.name, "ok" if s.ready else "warn", "") for s in statuses])
    for s in statuses:
        if not s.ready:
            st.caption(f"{s.name}: {s.message}")

    st.divider()
    st.caption(config.AI_DISCLOSURE)

# =============================================================================
# Hero + KPIs
# =============================================================================
hero(
    "Egyptian Voice Sender",
    "Write in Egyptian dialect, generate a natural voice note, and deliver it through the official "
    "WhatsApp Cloud API. Every file is labelled “Generated AI voice audio.”",
    eyebrow="AI voice studio",
)

contacts = db.list_contacts()
senders = db.list_authorized_senders()
ready_voices = sum(1 for s in statuses if s.ready)
kpis([
    ("Text engine", text_engine),
    ("Voice providers ready", f"{ready_voices} / {len(statuses)}"),
    ("Contacts", str(len(contacts))),
    ("Authorized senders", str(len(senders))),
])

tab_generate, tab_voicelab, tab_contacts, tab_senders, tab_log = st.tabs(
    ["Studio", "Voice lab", "Contacts", "Authorized senders", "Activity"]
)


@st.cache_data(ttl=120, show_spinner=False)
def cached_voices(_key_present: bool) -> list[dict]:
    if not _key_present:
        return []
    try:
        return [v.__dict__ for v in elevenlabs_service.list_voices()]
    except (elevenlabs_service.ElevenLabsSetupError, elevenlabs_service.ElevenLabsError):
        return []

# =============================================================================
# Studio
# =============================================================================
with tab_generate:
    # ---- Step 1: write -------------------------------------------------------
    step(1, "Write the message", f"Draft from a brief or paste text, then refine with {text_engine}.")
    col_text, col_tools = st.columns([3, 2], gap="large")

    with col_text:
        with st.expander(f"Draft with {text_engine} from a short brief", expanded=not st.session_state.get("message_text")):
            brief = st.text_area(
                "What should the voice note say? Any language works.",
                height=90,
                key="brief_text",
                placeholder="مثال: فكّر أحمد إن الاجتماع بكرة الساعة 5 ولازم يجيب العقد معاه",
            )
            if st.button(f"Write with {text_engine}", type="primary", disabled=not (brief.strip() and engine_ok)):
                with st.spinner(f"{text_engine} is writing..."):
                    try:
                        drafted, _ = write_message(brief, text_engine)
                        st.session_state["message_text"] = drafted
                        st.session_state.pop("refined_text", None)
                        st.rerun()
                    except RefineError as exc:
                        st.error(str(exc))

        with st.container(key="arabic_scope"):
            text = st.text_area(
                "Message text (Egyptian Arabic)",
                height=170,
                key="message_text",
                placeholder="اكتب الرسالة هنا...",
            )
        st.caption(f"{len(text)} characters")

    with col_tools:
        st.markdown("**Polish**")
        if st.button(f"Refine into Egyptian dialect with {text_engine}", disabled=not (text.strip() and engine_ok)):
            with st.spinner(f"{text_engine} is refining..."):
                try:
                    refined, engine_used = refine_to_egyptian(text, text_engine)
                    st.session_state["refined_text"] = refined
                    st.session_state["refined_engine"] = engine_used
                except RefineError as exc:
                    st.error(str(exc))
        if st.session_state.get("refined_text"):
            with st.container(key="refined_scope"):
                st.text_area(
                    f"Refined by {st.session_state.get('refined_engine', '')}",
                    value=st.session_state["refined_text"], height=140, key="refined_view",
                )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Use refined text", type="primary"):
                    st.session_state["message_text"] = st.session_state["refined_text"]
                    st.session_state.pop("refined_text", None)
                    st.rerun()
            with c2:
                if st.button("Discard"):
                    st.session_state.pop("refined_text", None)
                    st.rerun()
        if not engine_ok:
            st.warning(engine_msg)

    # ---- Step 2: voice -------------------------------------------------------
    step(2, "Generate the voice", "ElevenLabs natural voice first (soft Egyptian female or your clone); Azure, Groq, OpenAI and Windows as alternatives.")
    col_prov, col_voice, col_go = st.columns([2, 1.4, 1.2], gap="large")

    with col_prov:
        provider = st.selectbox(
            "Voice provider",
            PROVIDER_ORDER,
            index=PROVIDER_ORDER.index(default_provider()),
            help="Order of preference: ElevenLabs, Azure Egyptian, Groq, OpenAI, then the Windows fallback.",
        )
        status = next(s for s in statuses if s.name == provider)
        if not status.ready:
            st.warning(status.message)
        if provider == PROVIDER_WINDOWS:
            st.warning(status.warning)

    voice_options: dict = {}
    with col_voice:
        if provider == PROVIDER_ELEVENLABS:
            voices = cached_voices(elevenlabs_service.available())
            clones = {c["voice_id"] for c in db.list_voice_clones("elevenlabs")}
            if voices:
                labels = [("★ " if v["voice_id"] in clones else "") + elevenlabs_service.Voice(**v).label for v in voices]
                default_id = config.elevenlabs_voice_id()
                default_idx = next((i for i, v in enumerate(voices) if v["voice_id"] == default_id), 0)
                pick = st.selectbox("Voice", labels, index=default_idx, help="★ = your cloned voices. Female voices are listed first.")
                voice = voices[labels.index(pick)]["voice_id"]
            else:
                voice = st.text_input("Voice id", value=config.elevenlabs_voice_id(), placeholder="paste an ElevenLabs voice_id")
                if elevenlabs_service.available():
                    st.caption("Could not list voices. Paste a voice_id or add a voice in the Voice lab.")
            with st.expander("Delivery", expanded=False):
                model_ids = list(elevenlabs_service.MODELS)
                model_id = st.selectbox(
                    "Model", model_ids,
                    index=model_ids.index(config.elevenlabs_model()) if config.elevenlabs_model() in model_ids else 0,
                    format_func=lambda m: elevenlabs_service.MODELS[m],
                )
                softness = st.slider("Softness", 0.0, 1.0, 0.65, 0.05, help="Higher = calmer, steadier delivery.")
                warmth = st.slider("Closeness to the voice", 0.5, 1.0, 0.85, 0.05, help="Similarity to the original speaker.")
                expressive = st.slider("Expressiveness", 0.0, 0.6, 0.15, 0.05)
                pace = st.slider("Pace", 0.8, 1.15, 0.95, 0.05)
            voice_options = {
                "model_id": model_id,
                "settings": {"stability": softness, "similarity_boost": warmth, "style": expressive, "use_speaker_boost": True, "speed": pace},
            }
        elif provider == PROVIDER_GROQ:
            voice = st.selectbox(
                "Voice",
                GROQ_ARABIC_VOICES,
                index=GROQ_ARABIC_VOICES.index(config.groq_tts_voice())
                if config.groq_tts_voice() in GROQ_ARABIC_VOICES
                else 0,
            )
            st.caption("Saudi-dialect model: write the text in Egyptian dialect.")
        else:
            voice = st.text_input("Voice (blank = default)", value="")

    with col_go:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("Generate voice", type="primary", use_container_width=True, disabled=not text.strip()):
            with st.spinner(f"Generating with {provider}..."):
                try:
                    mp3 = generate_speech(text, provider, voice or None, options=voice_options)
                    st.session_state["last_audio"] = str(mp3)
                    st.toast(f"Saved {mp3.name}", icon="✅")
                except TTSSetupError as exc:
                    st.error(f"Setup problem: {exc}")
                except (TTSGenerationError, ValueError) as exc:
                    st.error(str(exc))

    last_audio = st.session_state.get("last_audio")
    if last_audio and Path(last_audio).exists():
        audio_bytes = Path(last_audio).read_bytes()
        pa, pb = st.columns([3, 1], gap="large")
        with pa:
            st.audio(audio_bytes, format="audio/mpeg")
            st.caption(f"{Path(last_audio).name} · {len(audio_bytes) / 1024:.0f} KB · {config.AI_DISCLOSURE}")
        with pb:
            st.download_button("Download MP3", audio_bytes, file_name=Path(last_audio).name, mime="audio/mpeg", use_container_width=True)

    # ---- Step 3: send --------------------------------------------------------
    step(3, "Send on WhatsApp", "Official Cloud API only, always through an authorized Meta phone_number_id.")
    col_from, col_to = st.columns(2, gap="large")

    with col_from:
        if senders:
            labels = [f"{s['display_name']} · {s['normalized_e164']} · id {s['phone_number_id']}" for s in senders]
            sender = senders[labels.index(st.selectbox("Authorized sender", labels))]
        else:
            sender = None
            st.warning("No authorized sender saved yet. Add one in the Authorized senders tab.")

    with col_to:
        locked = config.locked_recipient_number()
        if locked:
            try:
                recipient_input = normalize_phone(locked).normalized_e164
                st.text_input("Recipient (locked by LOCKED_RECIPIENT_NUMBER)", value=recipient_input, disabled=True)
            except ValueError as exc:
                recipient_input = ""
                st.error(f"LOCKED_RECIPIENT_NUMBER is invalid: {exc}")
        else:
            options = ["Type a number"] + [f"{c['name']} · {c['normalized_e164']}" for c in contacts]
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
                chips([(recipient_norm.normalized_e164, "ok", tag)])
            except ValueError as exc:
                st.error(str(exc))

    can_send = bool(sender and recipient_norm and last_audio and Path(last_audio).exists())
    col_a, col_b, col_c = st.columns(3, gap="large")

    with col_a:
        if st.button("Send audio via Cloud API", type="primary", use_container_width=True, disabled=not can_send):
            with st.spinner("Uploading and sending..."):
                try:
                    result = send_audio(sender["phone_number_id"], recipient_norm.normalized_e164, Path(last_audio))
                    db.log_send(result.recipient_e164, sender["phone_number_id"], last_audio, "sent", result.message_id)
                    st.success(f"Sent. Message id: {result.message_id}")
                except (WhatsAppSetupError, WhatsAppSendError, ValueError) as exc:
                    db.log_send(recipient_norm.normalized_e164, sender["phone_number_id"], last_audio, "failed", error=str(exc))
                    st.error(str(exc))

    with col_b:
        if st.button("Send test text", use_container_width=True, disabled=not (sender and recipient_norm)):
            try:
                mid = send_text(sender["phone_number_id"], recipient_norm.normalized_e164, f"Test from Egyptian Voice Sender. {config.AI_DISCLOSURE}")
                db.log_send(recipient_norm.normalized_e164, sender["phone_number_id"], None, "sent-text", mid)
                st.success(f"Text sent. Message id: {mid}")
            except (WhatsAppSetupError, WhatsAppSendError, ValueError) as exc:
                st.error(str(exc))

    with col_c:
        if recipient_norm and last_audio:
            st.link_button("Manual send: open WhatsApp chat", manual_chat_link(recipient_norm.normalized_e164), use_container_width=True)
            st.caption("Then attach this file yourself:")
            st.code(last_audio, language="text")


# =============================================================================
# Voice lab: natural voices and consent-gated cloning
# =============================================================================
with tab_voicelab:
    step(1, "Clone a voice", "Upload clean samples of the speaker, confirm consent, and the clone appears in Step 2.")
    if not elevenlabs_service.available():
        st.warning("Add ELEVENLABS_API_KEY to your keys file to enable natural voices and cloning.")
    st.caption(
        "For an authentic Egyptian accent, clone an Egyptian speaker you have permission from. "
        "Best results: 1–3 minutes of clear speech, one speaker, no music or echo. Instant cloning gets close, not identical."
    )
    with st.form("clone_voice", clear_on_submit=False):
        v1, v2 = st.columns(2, gap="large")
        clone_name = v1.text_input("Voice name", placeholder="e.g. Mona")
        clone_gender = v2.selectbox("Gender label", ["female", "male"])
        samples = st.file_uploader(
            "Audio samples (mp3, wav, m4a, ogg)", type=["mp3", "wav", "m4a", "ogg", "flac"], accept_multiple_files=True
        )
        remove_noise = st.checkbox("Remove background noise", value=True)
        consent = st.checkbox(elevenlabs_service.CONSENT_TEXT)
        submitted = st.form_submit_button("Clone voice", type="primary", disabled=not elevenlabs_service.available())
    if submitted:
        if not consent:
            st.error("Tick the consent confirmation first. Cloning without the speaker's permission is not allowed.")
        elif not samples:
            st.error("Upload at least one audio sample.")
        else:
            import tempfile

            with st.spinner("Cloning..."):
                try:
                    with tempfile.TemporaryDirectory() as tmp:
                        paths = []
                        for up in samples:
                            dest = Path(tmp) / up.name
                            dest.write_bytes(up.getbuffer())
                            paths.append(dest)
                        result = elevenlabs_service.clone_voice(
                            clone_name, paths, remove_noise=remove_noise,
                            labels={"language": "ar", "accent": "Egyptian", "gender": clone_gender},
                        )
                    db.add_voice_clone("elevenlabs", result.voice.voice_id, clone_name, len(samples), elevenlabs_service.CONSENT_TEXT)
                    cached_voices.clear()
                    msg = f"Cloned “{clone_name}”. Select it in Step 2 under ElevenLabs."
                    if result.requires_verification:
                        msg += " ElevenLabs asks you to verify this voice in their dashboard before use."
                    st.success(msg)
                except (ValueError, elevenlabs_service.ElevenLabsSetupError, elevenlabs_service.ElevenLabsError) as exc:
                    st.error(str(exc))

    step(2, "Your cloned voices", "Consent is recorded locally for each clone.")
    clones = db.list_voice_clones("elevenlabs")
    if clones:
        st.dataframe(
            [{k: c[k] for k in ("name", "voice_id", "sample_count", "consent_at")} for c in clones],
            use_container_width=True, hide_index=True,
        )
        pick = st.selectbox("Clone", [f"{c['name']} ({c['voice_id']})" for c in clones])
        if st.button("Delete this clone from ElevenLabs and this app"):
            vid = pick.rsplit("(", 1)[1].rstrip(")")
            try:
                elevenlabs_service.delete_voice(vid)
            except (elevenlabs_service.ElevenLabsSetupError, elevenlabs_service.ElevenLabsError) as exc:
                st.warning(f"ElevenLabs: {exc}")
            db.delete_voice_clone(vid)
            cached_voices.clear()
            st.rerun()
    else:
        st.caption("No clones yet.")

    step(3, "Premade natural voices", "Any voice from your ElevenLabs library shows up in Step 2. Female voices are listed first.")
    st.caption("Add Arabic female voices to your library in the ElevenLabs dashboard (Voice Library → Arabic), then they appear here.")

# =============================================================================
# Contacts
# =============================================================================
with tab_contacts:
    step(1, "Add a contact", "Egyptian local numbers are normalized to E.164 automatically.")
    with st.form("add_contact", clear_on_submit=True):
        f1, f2 = st.columns(2, gap="large")
        c_name = f1.text_input("Name")
        c_phone = f2.text_input("Phone", placeholder="01123040202 → stored as +201123040202")
        if st.form_submit_button("Save contact", type="primary"):
            try:
                saved = db.add_contact(c_name, c_phone)
                st.toast(f"Saved {saved['name']}: {saved['original_input']} → {saved['normalized_e164']}", icon="✅")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

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
# Authorized senders
# =============================================================================
with tab_senders:
    step(1, "Authorized WhatsApp Business senders", "Only numbers registered in Meta WhatsApp Manager can send.")
    st.caption(
        "The phone_number_id is what the API uses; the business number is shown for display and validation only. "
        "An SMS-registered number can receive OTP codes but is not a WhatsApp sender by itself."
    )
    with st.form("add_sender", clear_on_submit=True):
        g1, g2 = st.columns(2, gap="large")
        s_name = g1.text_input("Display name")
        s_pnid = g2.text_input("Meta phone_number_id (numeric)")
        s_phone = g1.text_input("Business phone number", placeholder="01123040202 or +201123040202")
        s_waba = g2.text_input("WABA id (optional)")
        if st.form_submit_button("Save authorized sender", type="primary"):
            try:
                saved = db.add_authorized_sender(s_name, s_pnid, s_phone, s_waba)
                st.toast(f"Saved {saved['display_name']}: {saved['original_input']} → {saved['normalized_e164']}", icon="✅")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    if senders:
        st.dataframe(
            [{k: s[k] for k in ("id", "display_name", "phone_number_id", "original_input", "normalized_e164", "waba_id")} for s in senders],
            use_container_width=True,
            hide_index=True,
        )
        pick = st.selectbox("Sender", [f"{s['id']}: {s['display_name']} ({s['normalized_e164']})" for s in senders])
        sender_id = int(pick.split(":")[0])
        chosen = next(s for s in senders if s["id"] == sender_id)
        h1, h2 = st.columns(2, gap="large")
        with h1:
            if st.button("Validate with Meta", use_container_width=True):
                try:
                    info = check_sender(chosen["phone_number_id"])
                    st.success(
                        f"Meta reports {info.get('display_phone_number', '?')} "
                        f"({info.get('verified_name', 'unverified')}), quality {info.get('quality_rating', 'n/a')}."
                    )
                except (WhatsAppSetupError, WhatsAppSendError) as exc:
                    st.error(str(exc))
        with h2:
            if st.button("Delete selected sender", use_container_width=True):
                db.delete_authorized_sender(sender_id)
                st.rerun()
    else:
        st.caption("No authorized sender saved yet.")

# =============================================================================
# Activity
# =============================================================================
with tab_log:
    step(1, "Recent sends", "Latest 50 deliveries, newest first.")
    log = db.list_send_log()
    if log:
        sent = sum(1 for r in log if r["status"].startswith("sent"))
        kpis([("Logged", str(len(log))), ("Delivered", str(sent)), ("Failed", str(len(log) - sent))])
        st.dataframe(log, use_container_width=True, hide_index=True)
    else:
        st.caption("No sends yet.")
