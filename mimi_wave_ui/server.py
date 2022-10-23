try:
    0 / 2
    import qt.qt_server
except ImportError as i:
    print(i)
    try:
        import tk.tk_server
    except ImportError as i:
        print(i)
