from Types import resolve
from phone_manager.manager import UserManagement


def load(json_file='users.json', book='default'):
    """
    Initialize a named phonebook instance.
    :param json_file str: JSON filename stored in data_dir (default: users.json)
    :param book str: phonebook name (default: 'default')
    :return str: status message
    """
    if book not in UserManagement.INSTANCES:
        UserManagement.INSTANCES[book] = UserManagement(json_file)
        return f"UserManagement '{book}' started."
    return f"UserManagement '{book}' already running."


def _get(book='default'):
    """Get a phonebook instance by name."""
    inst = UserManagement.INSTANCES.get(book)
    if inst is None:
        raise RuntimeError(f"Phonebook '{book}' not loaded. Call load() first.")
    return inst

def add_user(phone, name, status='A', role='user', info='', valid_from='', expires='', daily_from='', daily_to='', book='default'):
    return _get(book).add_user(phone, name, status, role, info, valid_from, expires, daily_from, daily_to)

def modify_user(phone, book='default', **kwargs):
    return _get(book).modify_user(phone, **kwargs)

def delete_user(phone, book='default'):
    return _get(book).delete_user(phone)

def get_user(book='default', **kwargs):
    return _get(book).get_user(**kwargs)

def get_all_users(book='default'):
    return _get(book).get_all_users()

def count_users(book='default'):
    return _get(book).count_users()

def export_users(file='users_backup.json', book='default'):
    return _get(book).export_users(file)

def import_users(data=None, file=None, mode='replace', book='default'):
    return _get(book).import_users(data, file, mode)

def check_access(phone, book='default'):
    return _get(book).check_access(phone)

def grant_access(phone, valid_from='', expires='', book='default'):
    return _get(book).grant_access(phone, valid_from, expires)

def get_inactive_users(book='default'):
    return _get(book).get_inactive_users()

def clear_users(book='default'):
    return _get(book).clear_users()

def unload(book='default'):
    if book in UserManagement.INSTANCES:
        del UserManagement.INSTANCES[book]
        return f"UserManagement '{book}' stopped."
    return f"UserManagement '{book}' not loaded."

def list_books():
    return list(UserManagement.INSTANCES.keys())


#######################
# LM helper functions #
#######################

def help(widgets=False):
    """[i] micrOS LM naming convention - built-in help message"""
    return resolve(('load json_file="users.json" book="default"',
                    'load json_file="garage_users.json" book="garage"',
                    'add_user phone="+36202002000" name="John Doe" status="A" role="user" book="default"',
                    'modify_user phone="+36202002000" status="B" book="default"',
                    'delete_user phone="+36202002000" book="default"',
                    'get_user name="John Doe" book="default"',
                    'get_all_users book="default"',
                    'count_users book="default"',
                    'export_users file="users_backup.json" book="default"',
                    'import_users file="users_backup.json" mode="merge" book="default"',
                    'grant_access phone="+36202002000" valid_from="2026-05-10T12:00" expires="2026-06-13T20:00" book="default"',
                    'check_access phone="+36202002000" book="default"',
                    'get_inactive_users book="default"',
                    'clear_users book="default"',
                    'unload book="default"',
                    'list_books'), widgets=widgets)
