def split_full_name(full_name: str):
    """Splits a full repository name into owner and repo name."""
    owner, repo = full_name.split('/')
    return owner, repo