//! No Microsoft sessions in this fork: splitscreen players are always offline.
use std::sync::Arc;

/// The launcher's other signed-in accounts (`HORIZON_ACCOUNT_SESSIONS`), for
/// splitscreen players. Horizon's launcher is not part of this fork, and no
/// build of it signs anybody in, so the list is always empty and every split
/// player uses its own offline profile (`split_profiles`).
pub(super) fn accounts() -> Vec<Arc<horizon_client::auth::AuthSession>> {
    Vec::new()
}

static READ: std::sync::OnceLock<()> = std::sync::OnceLock::new();

pub(super) fn unavailable() -> Vec<String> {
    Vec::new()
}

/// Nothing to read at start: no session file is ever opened, consumed or deleted.
pub(in crate::game) fn read_now() {
    let _ = READ.set(());
}
