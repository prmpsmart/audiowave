try:
    import qt.qt_client
except ImportError as i:
    print(i)
    try:
        import tk.tk_client
    except ImportError as i:
        print(i)
        ...
