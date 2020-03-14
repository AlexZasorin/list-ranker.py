import argparse

import os
import random
import struct


class SessionHistory:
    def __init__(self, list_: list = None, beginning: bool = True):
        if list_:
            self._session_history = list_
            if beginning:
                self._idx = 0
            else:
                self._idx = len(list_)
        else:
            self._session_history = list()
            self._idx = 0

    def has_next(self):
        if self._idx <= len(self._session_history)-1:
            return self._session_history[self._idx]
        return None

    def next(self):
        next_item = self._session_history[self._idx]
        self._idx += 1
        return next_item

    def previous(self):
        self._idx -= 1
        return self._session_history[self._idx]

    def append(self, num: int):
        if self.has_next():
            self._session_history[self._idx] = num
        else:
            self._session_history.append(num)
        self._idx += 1

        print(self._session_history)


def _setup_args():
    """
    Setup command-line arguments and return the parsed arguments.
    """

    parser = argparse.ArgumentParser(description='Tool to help you rank a list of items. Originally created to help '
                                                 'rank favorite anime, movies, and TV shows.')
    parser.add_argument('--mal', action='store_true', help='If you are ranking anime, use this flag to pre-sort your '
                                                           'list according to each titles score on MyAnimeList '
                                                           '(highest to lowest).')
    parser.add_argument('-l', '--list', action='store', type=str, nargs=1, default=None,
                        help='Specify the path to the text file containing the list you would like to rank.')
    return parser.parse_args()


def _get_file_name():
    file_list = os.listdir(os.getcwd())
    while True:
        file_name = str(input('Please enter a name for the file: ')) + '.rsave'

        # Check if a file with that name already exists and ask if user wants to overwrite it
        if file_name not in file_list:
            return file_name
        else:
            answer = str(input('\'' + file_name + '\' already exists, would you like to overwrite? (y/N): '))
            print()
            if answer.lower() == 'y':
                return file_name


def _check_header(file_name):
    with open(file_name, 'rb') as session_file:
        print(hex(int.from_bytes(session_file.read(2), byteorder='big')))
        print(struct.unpack('i', session_file.read(4))[0])

    with open(file_name, 'r') as session_file:
        session_file.read(6)
        print(session_file.read())


def ranked_lt(elem: str, piv: str):
    print('[1] {} or [2] {}?'.format(elem, piv))
    choice = input('> ')

    while True:
        if not (choice == '1' or choice == '2'):
            choice = input('> ')
        else:
            break

    if int(choice) == 1:
        return False
    return True


def insertion_sort(arr: list):
    for i in range(1, len(arr)):
        key = arr[i]
        j = i-1

        while j >= 0 and ranked_lt(key, arr[j]):
            arr[j+1] = arr[j]
            j = j-1

        arr[j+1] = key


def partition(arr: list, low: int, high: int, replay: bool, session: SessionHistory):
    i = low - 1

    if replay:
        piv_idx = session.next()
    else:
        piv_idx = random.randint(low, high)
        session.append(piv_idx)

    piv = arr[piv_idx]
    arr[piv_idx], arr[high] = arr[high], arr[piv_idx]

    for j in range(low, high):
        if replay:
            result = session.next()
        else:
            result = ranked_lt(arr[j], piv)
            session.append(int(result))

        if result:
            i = i + 1
            arr[i], arr[j] = arr[j], arr[i]

    arr[i + 1], arr[high] = arr[high], arr[i + 1]
    return i + 1


def quick_sort(arr: list, low: int, high: int, replay: bool, session: SessionHistory = None):
    if low < high:
        if session:
            if replay and not session.has_next():
                replay = False
        else:
            session = SessionHistory()

        piv = partition(arr, low, high, replay, session)

        quick_sort(arr, low, piv - 1, replay, session)
        quick_sort(arr, piv + 1, high, replay, session)


def main():
    # Setup command-line arguments and parse them
    args = _setup_args()

    # Turn list into string
    dir_ = None
    if args.list:
        dir_ = ''.join(args.list)

    # If a directory was specified, start a new session using the list given
    file_list = os.listdir(os.getcwd())
    if dir_:
        print('Creating new session...')
        file_name = _get_file_name()

        # Convert path to absolute path
        if not os.path.isabs(dir_):
            dir_ = os.path.abspath(dir_)

        # Check if path leads to a file ending with .txt
        if not str.endswith(dir_, '.txt'):
            print('Error: You must specify a path to a .txt file.')

        # Open list of items to be ranked and fetch the contents
        unranked_file = open(dir_, 'r')
        list_string = unranked_file.read()
        unranked_file.close()

        # Put the contents into a list and start the sorting process
        unranked_list = list_string.split('\n')
        quick_sort(unranked_list, 0, len(unranked_list) - 1, False)

        # Write the results to a new file
        with open('output.txt', 'w+') as unranked_file:
            for item in unranked_list:
                unranked_file.write('{}\n'.format(item))
    else:
        count = 1
        save_exists = False
        for file in file_list:
            if str.endswith(file, '.rsave'):
                print('[' + str(count) + '] ' + file)
                count += 1
                save_exists = True

        if save_exists:
            while True:
                response = input('Please enter the number of the save file you would like to load: ')
                if isinstance(response, int):
                    save_num = response
                    break
                else:
                    print('Error: Invalid input. Please enter a number.')
                print()
        else:
            print('Error: No text file specified and no previous session file found. Please specify a text file '
                  'containing the list you would like to rank with the \'-l\' or \'--list\' flags.')

    return

    # Open list of items to be ranked and fetch the contents
    unranked_file = open(dir_, 'r')
    list_string = unranked_file.read()
    unranked_file.close()

    # Put the contents into a list and start the sorting process
    unranked_list = list_string.split('\n')
    quick_sort(unranked_list, 0, len(unranked_list) - 1, False)

    # Write the results to a new file
    unranked_file = open('output.txt', 'w+')
    for item in unranked_list:
        unranked_file.write('{}\n'.format(item))

    unranked_file.close()


if __name__ == '__main__':
    main()
