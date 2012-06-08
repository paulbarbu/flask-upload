#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
from flask import Flask, redirect, url_for, render_template, request, session
from werkzeug import secure_filename
from simplekv.fs import FilesystemStore
from flaskext.kvsession import KVSessionExtension
import re
import os.path
import sqlite3
import logging

import err
import const

app = Flask(__name__)

store = FilesystemStore('data')
sess_ext = KVSessionExtension(store, app)


#TODO test this
@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))
    else:
        return redirect(url_for('upload'))


#TODO test this
@app.route('/register', methods=['POST', 'GET'])
def register():
    '''On form submit attempt to create the user if the provided credentials
    are valid
    '''

    message = None
    error = None
    state = {}

    if request.method == 'POST':
        nick = request.form['nick'].lower()
        email = request.form['email'].lower()
        password = request.form['password']

        state = {
            'nick': nick,
            'email': email
        }

        if is_valid_nick(nick):
            if is_valid_email(email):
                if is_valid_password(password):
                    import hashlib

                    password = hashlib.sha1(password).hexdigest()

                    conn = sqlite3.connect(const.DB_FILENAME)
                    db = conn.cursor()

                    result = add_user(db, nick, email, password)

                    if result is True:
                        conn.commit()
                        message = const.R_SUCCESS
                        logging.info(
                                '{0}({1}) has registered'.format(nick, email))
                    elif result is False:
                        error = err.DB
                    else:
                        error = result

                    conn.close()

                else:
                    error = err.PASS
            else:
                error = err.EMAIL
        else:
            error = err.NICK

        del password

    else:
        if is_logged_in():
            return redirect(url_for('upload'))

    return render_template('register.html', message=message, error=error,
                            state=state)


#TODO test this
@app.route('/login', methods=['POST', 'GET'])
def login():
    '''Log the user in after checking his credentials'''

    message = {}
    error = None

    if request.method == 'POST':
        import hashlib

        nick = request.form['nick'].lower()
        password = hashlib.sha1(request.form['password']).hexdigest()

        if 'remember' in request.form:
            session.permanent = True

        conn = sqlite3.connect(const.DB_FILENAME)
        db = conn.cursor()

        uid = get_user_id(db, nick, password)

        if uid:
            session['uid'] = uid

            message = const.L_SUCCESS

            nick = get_nick_by_id(db, uid)

            if nick:
                message += ' as ' + nick
                logging.info('{0} has logged in'.format(nick))
            else:
                message += '!'
                logging.info('Someone has logged in')

        elif uid is None:
            error = err.NO_USER
        else:
            error = err.DB

        conn.close()

    else:
        if is_logged_in():
            return redirect(url_for('upload'))

    return render_template('login.html', message=message, error=error)


#TODO: test this
@app.route('/upload', methods=['POST', 'GET'])
def upload():
    '''Upload the file received through POST'''

    sess_ext.cleanup_sessions()

    message = None
    error = None

    if request.method == 'POST' and is_logged_in():
        conn = sqlite3.connect(const.DB_FILENAME)
        db = conn.cursor()

        f = request.files['file_data']
        filename = secure_filename(f.filename)

        if f:
            if filename:
                upload_dir = os.path.join(os.getcwd(), const.UPLOAD_PATH,
                    get_nick_by_id(db, session['uid']))

                if not os.path.isdir(upload_dir):
                    #TODO: check write permissions
                    os.makedirs(upload_dir)

                #TODO: here write permissions should be checked too
                f.save(os.path.join(upload_dir, filename))

                #TODO: add the upload to the database
                message = const.U_SUCCESS
            else:
                error = err.INVALID_FILENAME
        else:
            error = err.NO_FILE

        conn.close()

    else:
        if is_logged_in():
            return render_template('upload.html')
        else:
            return redirect(url_for('login'))

    return render_template('upload.html', message=message, error=error)


#TODO: test this
@app.route('/logout')
def logout():
    if not is_logged_in():
        return redirect(url_for('login'))
    else:
        session.destroy()
        sess_ext.cleanup_sessions()

        return render_template('logout.html')


def is_valid_nick(nick):
    '''A nick is valid when it contains at least one alphanumeric character'''
    if not nick or not re.match('^[a-zA-Z0-9_-]+$', nick):
        return False

    return True


def is_valid_password(password):
    '''A password is valid when it contains at least six characters'''
    if len(password) < 6:
        return False

    return True


def is_valid_email(email):
    '''Validates an email address
    http://code.activestate.com/recipes/65215-e-mail-address-validation/#c6
    '''
    if re.match('^[a-zA-Z0-9._%-+]+@[a-zA-Z0-9._%-]+.[a-zA-Z]{2,6}$', email):
        return True

    return False


def is_valid_sqlite3(db):
    '''Validates the SQLite3 database file by checking the first bytes
    Check: 1.2.1 Magic Header String of http://www.sqlite.org/fileformat.html
    Note that I'm discarding the last byte, namely: '\0'
    '''

    with open(db, 'r') as f:
        if f.read(15) == 'SQLite format 3':
            return True

        return False

    return False


def add_user(db, nick, email, password):
    '''Add a user to the database and log the action
    Return True is the user was added succesfully, else Fasle
    '''

    try:
        db.execute('INSERT INTO user(nick, email, password) VALUES(?,?,?)',
            (nick, email, password))
    except sqlite3.IntegrityError as e:
        if 'email' in str(e):
            return err.UNIQUE_EMAIL
        elif 'nick' in str(e):
            return err.UNIQUE_NICK
        else:
            logging.exception(e)
            return False
    except Exception as e:
        logging.exception(e)
        return False

    return True


def get_user_id(db, nick, hashed_pass):
    '''Returns the matching user's ID, else None
    If an unexpected exception is caught False will be returned
    The password passed as argument must be already hashed
    '''

    try:
        db.execute('SELECT id FROM user WHERE nick=? AND password=?',
                (nick, hashed_pass))
    except Exception as e:
        logging.exception(e)
        return False

    rv = db.fetchone()

    if rv is None:
        return None

    return int(rv[0])


def get_nick_by_id(db, uid):
    '''Get's the user's nickname by his id
    If the user doesn't exists None will be returned
    In case of errors False will be returned
    '''

    try:
        db.execute('SELECT nick FROM user WHERE id=?', (uid,))
    except Exception as e:
        logging.exception(e)
        return False

    rv = db.fetchone()

    if rv is None:
        return None

    return str(rv[0])


#TODO: test this
def is_logged_in():
    '''Check whether the user sent a cookie that holds a Beaker created
    session id
    '''

    if 'uid' not in session:
        return False

    return True


if __name__ == '__main__':
    logging.basicConfig(filename='logs.log', level=logging.DEBUG,
            format='%(levelname)s: %(asctime)s - %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S')

    if not is_valid_sqlite3(const.DB_FILENAME):
        print err.SQLITE_FILE_USER
        logging.critical(err.SQLITE_FILE)
    else:
        app.debug = True
        app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1 Gb
        app.secret_key = "your random key here"

        #all these calls should be replaced by a cron job
        sess_ext.cleanup_sessions()

        app.run()

    #TODO: http://pyramid.readthedocs.org/en/1.3-branch/narr/testing.html
