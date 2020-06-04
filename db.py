import shelve
import os

def open_db(name):
    db = None

    try:
        filename = '{}.db'.format(name)
        folder = 'db'
        if not os.path.isdir(folder):
            if os.path.exists(folder):
                print ('File "{}" already exists as a file'.format(folder))
                return None

            os.mkdir(folder)

        path = os.path.join(folder, filename)
        print ('Opening DB "{}"'.format(path))
        db = shelve.open(path, writeback=True)

    except:
        import traceback
        traceback.print_exc()
        print ('ERROR Cannot open database "{}"'.format(path))
        db = None
        pass

    return db
