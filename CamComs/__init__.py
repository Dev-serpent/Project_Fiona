"""Fiona communications subsystem."""

from CamComs.codec import decode_envelope, encode_envelope
from CamComs.audit import DEFAULT_AUDIT_LOG_PATH, AuditLog
from CamComs.encryption import (
    CamComsCryptoError,
    CamComsIdentity,
    PublicKeyBundle,
    decrypt_message,
    decrypt_text,
    encrypt_message,
)
from CamComs.instructions import (
    CamComsInstructionError,
    instruction_from_text,
    instruction_to_text,
    press_instruction,
    validate_instruction,
)
from CamComs.paths import DEFAULT_CAMCOMS_DIR, ensure_camcoms_dir, private_key_path, public_key_path
from CamComs.receiver import CamComsReceiverError, HostMessageProcessor, run_host_receiver
from CamComs.replay import DEFAULT_REPLAY_PATH, ReplayGuard
from CamComs.service import (
    DEFAULT_FIONA_CONFIG_PATH,
    HealthCheck,
    HostService,
    HostServiceConfig,
    default_host_service_config,
    load_host_service_config,
    save_host_service_config,
)
from CamComs.systemd import (
    install_host_service_unit,
    read_host_service_logs,
    render_host_service_unit,
    run_user_service_command,
    service_unit_path,
)
from CamComs.trust import (
    DEFAULT_TRUSTED_DIR,
    list_trusted_senders,
    load_trusted_sender,
    remove_trusted_sender,
    save_trusted_sender,
    trusted_public_key_path,
)
from CamComs.transport import CamComsHttpClient, encrypt_and_send_instruction, send_encoded_message, send_envelope

__all__ = [
    "CamComsCryptoError",
    "CamComsHttpClient",
    "CamComsIdentity",
    "CamComsInstructionError",
    "CamComsReceiverError",
    "AuditLog",
    "DEFAULT_CAMCOMS_DIR",
    "DEFAULT_AUDIT_LOG_PATH",
    "DEFAULT_FIONA_CONFIG_PATH",
    "DEFAULT_REPLAY_PATH",
    "DEFAULT_TRUSTED_DIR",
    "HealthCheck",
    "HostMessageProcessor",
    "HostService",
    "HostServiceConfig",
    "PublicKeyBundle",
    "ReplayGuard",
    "decode_envelope",
    "default_host_service_config",
    "decrypt_message",
    "decrypt_text",
    "encode_envelope",
    "ensure_camcoms_dir",
    "encrypt_message",
    "encrypt_and_send_instruction",
    "instruction_from_text",
    "instruction_to_text",
    "load_trusted_sender",
    "list_trusted_senders",
    "load_host_service_config",
    "press_instruction",
    "private_key_path",
    "public_key_path",
    "run_host_receiver",
    "save_host_service_config",
    "save_trusted_sender",
    "remove_trusted_sender",
    "send_encoded_message",
    "send_envelope",
    "install_host_service_unit",
    "render_host_service_unit",
    "run_user_service_command",
    "read_host_service_logs",
    "service_unit_path",
    "trusted_public_key_path",
    "validate_instruction",
]
