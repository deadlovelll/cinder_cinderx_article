def after_fork_child() -> None:
    try:
        import cinderjit

        cinderjit.after_fork_child()
    except Exception:
        pass
