"""Non-human session role values for SET LOCAL app.role (not membership Role)."""

# Used by background workers / scheduler. Not a valid access.Role and never
# accepted from HTTP (ActorContext.role is always Role enum from a membership row).
SESSION_ROLE_WORKER = "worker"
SESSION_ROLE_SCHEDULER = "scheduler"
