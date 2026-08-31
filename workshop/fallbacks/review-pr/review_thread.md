# Synthetic review thread

**API owner:** Please use the existing `/organizations/me` identity boundary.
Adding a selector for convenience would be a separate authorization design.

**Author:** The selector is optional and the normal call still uses the key, so I
considered it backward compatible.

**Analytics owner:** Signed workload is intentional: requester backlog is
positive and provider capacity is negative. Reporting a magnitude does not
necessarily mean taking an absolute value before deciding what the quantity
represents.

This thread is targeted process context, not permission to skip reading the
issue and diff.
