import argparse

import os
import random
import sqlite3
import sys
import time

import jikanpy

from enum import Enum
from jikanpy import Jikan

DB_NAME = 'sessions.db'


class Action(Enum):
    PREVIOUS = 0
    EXIT = 1


# TODO: Delete session from DB upon completion
# TODO: Ability to delete sessions


class SessionHistory:
    def __init__(self, session_name: str, new: bool = True, list_: list = None, random_pivot: bool = True):
        self._session_name = session_name
        self._unranked_list = list_
        self._idx = 0
        self.random_pivot = random_pivot

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        if new:
            # Check if list_ is none
            if not list_:
                raise ValueError('New session requires non-empty list_ parameter.')

            # Create session in SQLite DB
            self._size = 0

            cur.execute('INSERT INTO SESSION VALUES (?, ?, ?, ?)',
                        (session_name, 'Quick Sort', '\n'.join(self._unranked_list), self.random_pivot))
            conn.commit()
        else:
            # Load session from SQLite DB
            cur.execute('SELECT S.List, S.RandomPivot '
                        'FROM SESSION AS S '
                        'WHERE S.Name = ?', (session_name,))

            row = cur.fetchone()
            conn.commit()

            self._unranked_list = row[0].split('\n')
            self.random_pivot = bool(row[1])

            cur.execute('SELECT H.Idx '
                        'FROM History AS H '
                        'WHERE H.SessionName = ? '
                        'ORDER BY H.Idx DESC', (session_name,))

            row = cur.fetchone()
            conn.commit()

            self._size = row[0]

        conn.close()

    def peek_next(self):
        if self._idx <= self._size:
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute('SELECT H.Value '
                        'FROM SESSION AS S, HISTORY AS H '
                        'WHERE S.Name = ? AND S.Name = H.SessionName AND H.Idx = ?'
                        'ORDER BY H.Idx',
                        (self._session_name, self._idx))

            row = cur.fetchone()
            conn.commit()
            conn.close()

            if row:
                return row[0]

        return None

    def next(self):
        next_item = self.peek_next()

        if next_item is not None:
            self._idx += 1

        return next_item

    def peek_previous(self):
        if self._idx > 0:
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute('SELECT H.Value '
                        'FROM SESSION AS S, HISTORY AS H '
                        'WHERE S.Name = ? AND S.Name = H.SessionName AND H.Idx = ?',
                        (self._session_name, self._idx - 1))

            row = cur.fetchone()

            conn.commit()

            if row:
                return row[0]

            conn.close()
        return None

    def previous(self):
        prev_item = self.peek_previous()

        if prev_item is not None:
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()

            # Check if the current row is a pivot, if so remove the row before it as long as its a comparison
            cur.execute('SELECT H.Type '
                        'FROM SESSION AS S, HISTORY AS H '
                        'WHERE S.Name = ? AND S.Name = H.SessionName AND H.Idx IN (?,?)'
                        'ORDER BY H.Idx ',
                        (self._session_name, self._idx - 1, self._idx - 2))

            if cur.fetchone()[0] == 'comparison' and cur.fetchone()[0] == 'pivot':
                cur.execute('DELETE FROM HISTORY '
                            'WHERE SessionName = ? AND Idx = ?',
                            (self._session_name, self._idx - 2))
                self._size -= 1

            cur.execute('DELETE FROM HISTORY '
                        'WHERE SessionName = ? AND Idx = ?',
                        (self._session_name, self._idx - 1))
            conn.commit()

            conn.commit()
            conn.close()

            self._idx = 0
            self._size -= 1
            self._unranked_list = self.get_list()

        return prev_item

    def append(self, num: int, pivot: bool = False):
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        cur.execute('INSERT INTO HISTORY (SessionName, Value, Idx, Type)'
                    'VALUES (?, ?, ?, ?)',
                    (self._session_name, num, self._idx, 'pivot' if pivot else 'comparison'))
        conn.commit()

        self._idx += 1
        self._size += 1

        conn.close()

    def get_list(self):
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        cur.execute('SELECT S.List '
                    'FROM SESSION AS S '
                    'WHERE S.Name = ?', (self._session_name,))

        row = cur.fetchone()
        conn.commit()

        return row[0].split('\n')


def _setup_args():
    """
    Setup command-line arguments and return the parsed arguments.
    """

    # TODO: If no list is given, let it pull a list from MAL
    parser = argparse.ArgumentParser(description='Tool to help you rank a list of items. Originally created to help '
                                                 'rank favorite anime, movies, and TV shows.')
    parser.add_argument('--mal', action='store_true', help='If you are ranking anime, use this flag to fetch your '
                                                           'completed anime list and pre-sort it according to each '
                                                           'titles\' score on MyAnimeList for quicker sorting.'
                                                           '(highest to lowest).')
    parser.add_argument('-l', '--list', action='store', type=str, nargs=1, default=None,
                        help='Specify the path to the text file containing the list you would like to rank.')
    return parser.parse_args()


def is_int(num: str):
    try:
        int(num)
    except ValueError:
        return False

    return True


def get_user_input(elem: str, piv: str):
    print('[1] {} or [2] {}?'.format(elem, piv))
    choice = input('> ')

    while True:
        if not (choice in ['1', '2', '<', 'q']):
            choice = input('> ')
        else:
            break

    if is_int(choice):
        if int(choice) == 1:
            return False
        return True
    elif choice == '<':
        return Action.PREVIOUS
    elif choice == 'q':
        return Action.EXIT


# TODO: Add ability for replay mode
# TODO: Use when array size is <= 5
def insertion_sort(arr: list, replay: bool):
    for i in range(1, len(arr)):
        key = arr[i]
        j = i - 1

        while j >= 0 and get_user_input(key, arr[j]):
            arr[j + 1] = arr[j]
            j = j - 1

        arr[j + 1] = key


def partition(arr: list, low: int, high: int, replay: bool, session: SessionHistory):
    i = low - 1

    if replay and session.peek_next() is None:
        replay = False

    if replay:
        piv_idx = session.next()
    else:
        if session.random_pivot:
            piv_idx = random.randint(low, high)
            print('Random pivot chosen')
        else:
            piv_idx = int(low + ((high - low) / 2))
            print('Median pivot chosen')
        session.append(piv_idx, pivot=True)

    piv = arr[piv_idx]
    arr[piv_idx], arr[high] = arr[high], arr[piv_idx]

    for j in range(low, high):
        if replay and session.peek_next() is None:
            replay = False

        if replay:
            result = session.next()
        else:
            result = get_user_input(arr[j], piv)
            if result in [Action.PREVIOUS, Action.EXIT]:
                return result
            else:
                session.append(int(result))

        if result:
            i = i + 1
            arr[i], arr[j] = arr[j], arr[i]

    arr[i + 1], arr[high] = arr[high], arr[i + 1]
    return i + 1


def quick_sort(arr: list, low: int, high: int, replay: bool, session: SessionHistory):
    if low < high:
        piv = partition(arr, low, high, replay, session)

        if piv in [Action.PREVIOUS, Action.EXIT]:
            return piv

        qs_out = quick_sort(arr, low, piv - 1, replay, session)
        if qs_out in [Action.PREVIOUS, Action.EXIT]:
            return qs_out

        qs_out = quick_sort(arr, piv + 1, high, replay, session)
        if qs_out in [Action.PREVIOUS, Action.EXIT]:
            return qs_out


def main():
    # Setup command-line arguments and parse them
    args = _setup_args()

    file_list = [f for f in os.listdir('.') if os.path.isfile(f)]

    # Check if DB exists
    # TODO: Check if its an actual SQLite DB with the same schema
    db_exists = DB_NAME in file_list

    # Connect to DB
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if not db_exists:
        # Create tables since there wasn't a db file present initially
        cur.execute('CREATE TABLE SESSION'
                    '(Name          TEXT PRIMARY KEY,'
                    'Algorithm      TEXT,'
                    'List           TEXT,'
                    'RandomPivot    BOOLEAN)')

        cur.execute('CREATE TABLE HISTORY'
                    '(ID            INTEGER NOT NULL PRIMARY KEY,'
                    'SessionName    TEXT,'
                    'Value          INTEGER NOT NULL,'
                    'Idx            INTEGER NOT NULL,'
                    'Type           TEXT NOT NULL,'
                    'FOREIGN KEY(SessionName) REFERENCES SESSION(Name))')

        conn.commit()

    # Load names of existing sessions
    cur.execute('SELECT Name '
                'FROM SESSION')
    sessions = [row[0] for row in cur.fetchall()]
    conn.commit()

    # If pre-existing sessions exist, ask the user if they want to start a new session or load an old one
    new_session = True
    if len(sessions) > 0:
        answer = input('Would you like to load a pre-existing session? (Y/n): ')
        if answer.lower() in ['yes', 'y']:
            new_session = False

    # Turn list into string
    dir_ = None
    if args.list:
        dir_ = ''.join(args.list)

    replay = False
    if not new_session:
        if len(sessions) != 1:
            print('Existing sessions:')
            for num, session in enumerate(sessions, start=1):
                print('[' + str(num) + '] ' + session)

        session_num = 0
        if len(sessions) == 1:
            session_num = 1
        else:
            while session_num == 0:
                answer = input('Enter the number of the session you wish to load: ')

                try:
                    answer = int(answer)
                except ValueError:
                    print('Error: Invalid input. Please enter an integer.')
                    continue

                if 0 < answer <= len(sessions):
                    session_num = answer
                else:
                    print('Error: Invalid input. Please enter a number between 1 and ' + str(len(sessions)) + '.')

        session_name = sessions[session_num - 1]
        print('Loading session "' + session_name + '"')

        # Load session from SQLite DB
        session = SessionHistory(session_name, False)
        unranked_list = session.get_list()
        replay = True
    else:
        # Get session name
        while True:
            answer = input('Please enter a name for this session: ')

            if answer.lower() in sessions:
                print('A session with that name already exists, please try again.')
                continue

            break

        if args.mal:
            jikan = Jikan()
            while True:
                name = input('Please enter your MAL Username: ')

                # cached = False
                try:
                    # cached = bool(jikan.user(username=name)['request_cached'])
                    jikan.user(username=name)
                except jikanpy.exceptions.APIException as e:
                    time.sleep(4)
                    if e.args[0] == 404:
                        print('User not found, please try again.')
                    else:
                        print(str(e) + '\nAn error occurred trying to find user. Please try again.')
                    continue
                break

            # if not cached:
            #     print('Request not cached, sleeping...')
            #     time.sleep(2)
            time.sleep(4)

            try:
                anime_list = jikan.user(username=name, request='animelist', argument='completed')
            except jikanpy.APIException as e:
                print(str(e) + '\nAn error occurred trying to fetch your anime list.')
                return

            print('Fetching your completed anime from MAL, this may take a while...')

            # if not bool(anime_list['request_cached']):
            #     print('Request not cached, sleeping...')
            #     time.sleep(2)
            time.sleep(4)

            counter = 0
            anime_scores = dict()
            for local_anime in anime_list['anime']:
                while True:
                    try:
                        global_anime = jikan.anime(local_anime['mal_id'])
                    except jikanpy.APIException as e:
                        if e.args[0] == 403:
                            print(str(e) + '\n403 error received, retrying in 5 seconds...')
                        elif e.args[0] == 429:
                            print('Rate limited, waiting 5 seconds...')
                        else:
                            print(str(e) + '\nRetrying in 5 seconds...')
                        time.sleep(4)
                        continue

                    break

                main_title = global_anime['title']
                alt_title = global_anime['title_english']

                if main_title != alt_title and alt_title is not None:
                    anime_scores[main_title + ' (' + alt_title + ')'] = global_anime['score']
                else:
                    anime_scores[main_title] = global_anime['score']

                counter += 1
                sys.stdout.write('\r' + str(counter) + '/' + str(len(anime_list['anime'])) + ' retrieved!')

                # if not bool(global_anime['request_cached']):
                #     print('Request not cached, sleeping...')
                #     time.sleep(2)
                time.sleep(4)

            unranked_list = [anime[0] for anime in sorted(anime_scores.items(), key=lambda x: x[1], reverse=True)]
        else:
            # Check if a directory was specified
            if not dir_:
                print('No list specified for ranking. Please specify a list using the -l or -list parameter.')
                return

            # Convert path to absolute path
            if not os.path.isabs(dir_):
                dir_ = os.path.abspath(dir_)

            # Check if path leads to a file ending with .txt
            if not str.endswith(dir_, '.txt'):
                print('Error: You must specify a path to a .txt file.')
                return

            # Open list of items to be ranked and fetch the contents
            unranked_file = open(dir_, 'r')
            list_string = unranked_file.read()
            unranked_file.close()

            # Put the contents into a list
            unranked_list = list_string.split('\n')

        # Create session
        session = SessionHistory(session_name=str(answer.lower()),
                                 new=True, list_=unranked_list,
                                 random_pivot=(not args.mal))

    while True:
        qs_out = quick_sort(unranked_list, 0, len(unranked_list) - 1, replay, session)

        if qs_out == Action.EXIT:
            return

        if qs_out == Action.PREVIOUS:
            session.previous()
            unranked_list = session.get_list()
            replay = True
            continue

        break

    # Write the results to a new file
    with open('output.txt', 'w+') as unranked_file:
        for item in unranked_list:
            unranked_file.write('{}\n'.format(item))


if __name__ == '__main__':
    main()
