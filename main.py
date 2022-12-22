from flask import Flask, render_template, url_for, request, flash, session, redirect
import psycopg2
import psycopg2.extras
import re
from werkzeug.security import generate_password_hash, check_password_hash
from time import sleep
from random import shuffle
from io import TextIOWrapper
from config import DB_NAME, DB_USER, DB_PASS, DB_HOST, DB_PORT

main = Flask(__name__)

main = Flask(__name__)
main.secret_key = 'bony-m'

try:
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)
except:
    print('no connection')

@main.route('/', methods=['GET', 'POST'])
def home():
    if 'loggedin' in session:
        error = False
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute('SELECT * FROM route')
        routes = cursor.fetchall()
        route_and_data = list()
        for route in routes:
            route = route[0]
            temp = [route]
            cursor.execute('SELECT depart_time, station_name FROM station WHERE route_id = %s AND'
                           ' station_number = 1', (route, ))
            start_station = cursor.fetchone()
            cursor.execute('SELECT depart_time, station_name FROM station WHERE route_id = %s '
                           ' ORDER BY station_number DESC LIMIT 1', (route, ))
            finish_station = cursor.fetchone()
            cursor.execute('SELECT train_name, train_type, train_id FROM train WHERE route_id = %s '
                           , (route,))
            train_info = cursor.fetchall()
            temp.append(train_info)
            temp.append(start_station)
            temp.append(finish_station)
            route_and_data.append(temp)

        if request.method == 'POST':
            date = request.form['date']
            come_from = request.form['from']
            come_to = request.form['to']
            if come_from and not re.match(r'[0-9]+', come_from) \
            or come_to and not re.match(r'[0-9]+', come_to) \
            or date:
                come_from = '%' + come_from + '%'
                come_to = come_to
                date += ' 00:00:00'
                cursor.execute("SELECT route_id FROM station WHERE station_name ILIKE %s AND" 
                               " station_number = 1 AND depart_time >= %s AND"
                               " depart_time -  INTERVAL '1 DAY' < %s",
                               (come_from, date, date))
                routes_id = cursor.fetchall()

                valid_routes = []
                for route in routes_id:
                    route = route[0]
                    cursor.execute('SELECT station_name FROM station WHERE route_id = %s '
                                   ' ORDER BY station_number DESC LIMIT 1', (route,))
                    finish_station = cursor.fetchone()
                    if finish_station:
                        if come_to.lower() in finish_station[0].lower():
                            valid_routes.append(route)

                route_and_data = list()
                for route in valid_routes:
                    temp = [route]
                    cursor.execute('SELECT depart_time, station_name FROM station WHERE route_id = %s AND'
                                   ' station_number = 1', (route,))
                    start_station = cursor.fetchone()
                    cursor.execute('SELECT depart_time, station_name FROM station WHERE route_id = %s '
                                   ' ORDER BY station_number DESC LIMIT 1', (route,))
                    finish_station = cursor.fetchone()
                    cursor.execute('SELECT train_name, train_type, train_id FROM train WHERE route_id = %s '
                                   , (route,))
                    train_info = cursor.fetchall()
                    temp.append(train_info)
                    temp.append(start_station)
                    temp.append(finish_station)
                    route_and_data.append(temp)


            elif not date and not come_to and not come_from:
                pass
            else:
                error = True


        # cursor.execute('SELECT * FROM route JOIN train USING (route_id)')
        # routes_and_trains = cursor.fetchall()
       # print(routes_and_trains)
        return render_template('home.html', route_and_data=route_and_data , error=error)

    return redirect(url_for('login'))


@main.route('/login/', methods=['GET', 'POST'])
def login():
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    errors = [False for _ in range(3)]
    if request.method == 'POST' and 'login' in request.form and 'password' in request.form:
        user_login = request.form['login']
        password = request.form['password']

        cursor.execute('SELECT * FROM user_db WHERE user_login = %s', (user_login,))
        account = cursor.fetchone()
        if account:
            password_rs = account['user_password']
            # If account exists in users table in out database
            if check_password_hash(password_rs, password):
                # Create session data, we can access this data in other routes
                session['loggedin'] = True
                session['user_login'] = user_login
                cursor.execute('SELECT is_admin FROM user_db WHERE user_login = %s', (user_login,))
                is_admin = cursor.fetchone()
                session['isadmin'] = is_admin[0]
                # Redirect to home page
                return redirect(url_for('home'))
            else:
                # Account doesnt exist or username/password incorrect
                errors[0] = True
        else:
            errors[1] = True

    elif request.method == 'POST':
        errors[2] = True
    return render_template('login.html', errors=errors)


@main.route('/register', methods=['GET', 'POST'])
def register():

    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # Check if "username", "password" and "email" POST requests exist (user submitted form)
    errors = [False for _ in range(7)]

    if request.method == 'POST':
        if not request.form['firstname']:
            errors[0] = True
        elif not request.form['secondname']:
            errors[1] = True
        elif not request.form['login']:
            errors[2] = True
        elif not request.form['age']:
            errors[3] = True
        elif not request.form['password']:
            errors[4] = True
        elif not request.form['gender']:
            errors[5] = True
        else:
            firstname = request.form['firstname']
            secondname = request.form['secondname']
            user_login = request.form['login']
            age = request.form['age']
            gender = request.form['gender']
            password = request.form['password']
            _hashed_password = generate_password_hash(password)
            cursor.execute('SELECT * FROM user_db WHERE user_login = %s', (user_login,))
            account = cursor.fetchone()
            if account:
                errors[6] = True
            elif not re.match(r'[A-Za-z0-9]+', user_login):
                errors[2] = True
            elif not re.match(r'[A-Za-z0-9]+', password) or len(password) < 8:
                errors[4] = True
            elif not re.match(r'[0-9]+', age):
                errors[3] = True
            else:
                # Account don't exist and the form data is valid, now insert new account into users table
                cursor.execute("INSERT INTO user_db (user_login, user_password, first_name, second_name,"
                               "gender, age) VALUES (%s,%s,%s,%s,%s,%s)",
                               (user_login, _hashed_password, firstname, secondname,
                                gender, age))
                conn.commit()
                session['loggedin'] = True
                session['user_login'] = user_login
                if user_login.lower() in ['admin', 'moderator', 'administrator']:
                    cursor.execute("UPDATE user_db SET is_admin = 'True' WHERE user_login = %s", (user_login,))
                    conn.commit()
                    session['isadmin'] = True
                else:
                    session['isadmin'] = False
                return redirect(url_for('home'))
    return render_template('register.html', errors=errors)


@main.route('/logout')
def logout():
    # Remove session data, this will log the user out
    session.clear()
    return redirect(url_for('login'))


@main.route('/pick_seat/<int:train_id>', methods=['GET', 'POST'])
def pick_seat(train_id):
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('SELECT vagon_number_of_seats FROM vagon WHERE train_id = %s', (train_id,))
    vagon_and_seats = cursor.fetchall()
    num_vagons = len(vagon_and_seats)
    print(vagon_and_seats)
    error = False
    count_seats = 0
    if request.method == 'POST':

        vagon_number = request.form.get('vagonnumber')
        cursor.execute('SELECT vagon_number_of_seats FROM vagon WHERE vagon_number = %s AND train_id = %s',
                       (vagon_number, train_id ))
        vagon_and_seats = cursor.fetchall()
        print(vagon_and_seats)
        booked_seat = request.form.getlist('seats')
        if len(booked_seat) > 1:
            error = True
        elif len(booked_seat) == 1:
            booked_seat = booked_seat[0]
            return redirect(url_for('buy_ticket', train_id=train_id, seat=booked_seat))


        print(vagon_number)
        cursor.execute('SELECT SUM(vagon_number_of_seats) FROM vagon WHERE vagon_number < %s AND train_id = %s',
                       (vagon_number, train_id ))

        count_seats = cursor.fetchone()
        if count_seats[0] is None:
            count_seats = 0
        else:
            count_seats = count_seats[0] // 4
        print(count_seats)


    cursor.execute('SELECT seat_number FROM ticket WHERE train_id = %s', (train_id,))
    not_avail_seats = cursor.fetchall()
    not_avail_seats = sorted(not_avail_seats)
    not_avail_seats_in_vagon = list()
    for seat in not_avail_seats:
        if int(seat[0][:-1]) < vagon_and_seats[0][0]:
            not_avail_seats_in_vagon.append(seat[0])
        else:
            break
    #not_avail_seats_in_vagon = ['1A', '2B', '3C', '10A']
    vagon_and_seats[0].append(not_avail_seats_in_vagon)
    print(vagon_and_seats)
    return render_template('train_seats.html', vagon_and_seats=vagon_and_seats,
                           num_vagons=num_vagons, train_id=train_id, error=error,
                           count_seats=count_seats)

@main.route('/buy_ticket/<int:train_id>/<string:seat>', methods=['GET', 'POST'])
def buy_ticket(train_id, seat):
    if not session['loggedin']:
        redirect(url_for('home'))
    else:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('SELECT * FROM train WHERE train_id = %s', (train_id,))
        train_info = cursor.fetchone()
        route_id = train_info['route_id']
        cursor.execute('SELECT station_name, depart_time FROM route JOIN station USING(route_id) '
                       'WHERE station_number = 1 AND route_id = %s', (route_id,))
        start_station = cursor.fetchone()
        cursor.execute('SELECT station_name, depart_time FROM route JOIN station USING(route_id) '
                       'WHERE route_id = %s ORDER BY station_number DESC LIMIT 1', (route_id,))
        finish_station = cursor.fetchone()
        if seat[-1] == 'A' or seat[-1] == 'D':
            price = 2400
        else:
            price = 2200
        return render_template('buy_ticket.html', train_info=train_info,
                               start_station=start_station, finish_station=finish_station, seat=seat,
                               price=price)

@main.route('/add_to_order/<int:train_id>/<string:seat>/<int:price>', methods=['GET', 'POST'])
def add_to_order(train_id, seat, price):
    if not session['loggedin']:
        redirect(url_for('home'))
    else:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('INSERT INTO ticket (price, seat_number, train_id, user_login, ticket_date) VALUES'
                       '(%s, %s, %s, %s, LOCALTIMESTAMP)', (price, seat, train_id, session['user_login']))
        conn.commit()
        return redirect(url_for('home'))


@main.route('/profile', methods=['GET'])
def profile():
    if not session['loggedin']:
        redirect(url_for('home'))
    else:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('SELECT * FROM user_db WHERE user_login = %s', (session['user_login'], ))
        account = cursor.fetchone()
        return render_template('profile.html', account=account)


@main.route('/about', methods=['GET'])
def about():
    return render_template('about.html', isadmin=session['isadmin'])


@main.route('/orders', methods=['GET'])
def orders():
    if not session['loggedin']:
        redirect(url_for('home'))
    else:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('SELECT train_id, ticket_id, seat_number FROM ticket WHERE user_login = %s', (session['user_login'],))
        ticket_info = cursor.fetchall()
        route_names = list()
        start_from = list()
        for info in ticket_info:
            cursor.execute('SELECT route_name, route_id FROM route JOIN train USING(route_id) WHERE train_id = %s',
                           (info['train_id'],))
            route_name = cursor.fetchone()
            route_names.append(route_name)
            cursor.execute('SELECT depart_time FROM station  WHERE station_number = 1 AND route_id = %s',
                           (route_name['route_id'],))
            start = cursor.fetchone()
            start_from.append(start)

        return render_template('orders.html', ticket_info=ticket_info, route_names=route_names,
                               start_from=start_from)


@main.route('/create_new_route', methods=['GET', 'POST'])
def create_new_route():
    if not session['isadmin']:
        redirect(url_for('home'))
    else:
        if request.method == 'POST':
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            route_name = request.form.get('route_name')
            if route_name is not None:
                cursor.execute('INSERT INTO route (route_name) VALUES'
                               '(%s) RETURNING route_id', (route_name, ))
                route_id = cursor.fetchone()[0]
                conn.commit()
                session['number_of_created_station'] = 1
                session['new_stations'] = list()
                return redirect(url_for('create_new_stations', route_id=route_id))

        return render_template('create_new_route.html')


@main.route('/create_new_stations/<int:route_id>', methods=['GET', 'POST'])
def create_new_stations(route_id):
    if not session['isadmin']:
        redirect(url_for('home'))
    else:
        error = False
        if request.method == 'POST':
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            button = request.form.get('button')
            if button is not None:
                if button == 'next':
                    station_name = request.form.get('station_name')
                    depart_time = request.form.get('depart_time')
                    session['new_stations'].append([station_name, depart_time])
                    session['number_of_created_station'] += 1
                    # try:
                    #     cursor.execute('INSERT INTO station (depart_time, route_id, station_number, station_name ) VALUES'
                    #                    '(%s, %s, %s, %s )', (depart_time, route_id, session['number_of_created_station'], station_name))
                    # except:
                    #     error = True

                elif button == 'commit':
                    station_name = request.form.get('station_name')
                    depart_time = request.form.get('depart_time')
                    session['new_stations'].append([station_name, depart_time])
                    # try:
                    #     cursor.execute(
                    #         'INSERT INTO station (depart_time, route_id, station_number, station_name ) VALUES'
                    #         '(%s, %s, %s, %s )',
                    #         (depart_time, route_id, session['number_of_created_station'], station_name))
                    # except:
                    #     error = True
                    first_station = 1
                    for station in session['new_stations']:
                        try:
                            cursor.execute(
                                'INSERT INTO station (depart_time, route_id, station_number, station_name ) VALUES'
                                '(%s, %s, %s, %s )',
                                (station[1], route_id, first_station, station[0]))
                            first_station += 1
                        except:
                            error = True
                        if not error:
                            conn.commit()
                    return redirect(url_for('about'))

        return render_template('create_new_stations.html',
                               number_of_created_station=session['number_of_created_station'], error=error)


@main.route('/create_new_train', methods=['GET', 'POST'])
def create_new_train():
    if not session['isadmin']:
        redirect(url_for('home'))
    else:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('SELECT * from route')
        routes = cursor.fetchall()
        return render_template('create_new_train.html', routes=routes)


@main.route('/create_train/<int:route_id>', methods=['GET', 'POST'])
def new_train(route_id):
    if not session['isadmin']:
        redirect(url_for('home'))
    else:
        if request.method == 'POST':
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            train_name = request.form.get('train_name')
            train_type = request.form.get('train_type')
            if train_name is not None and train_type is not None:
                cursor.execute('INSERT INTO train (train_name, train_type,'
                               'route_id) VALUES'
                               '(%s, %s, %s) RETURNING train_id', (train_name, train_type, route_id))
                train_id = cursor.fetchone()[0]
                conn.commit()
                session['number_of_created_vagon'] = 1
                session['new_vagons'] = list()
                return redirect(url_for('create_new_vagons', train_id=train_id))

        return render_template('create_train.html')


@main.route('/create_new_vagons/<int:train_id>', methods=['GET', 'POST'])
def create_new_vagons(train_id):
    if not session['isadmin']:
        redirect(url_for('home'))
    else:
        error = False
        if request.method == 'POST':
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            button = request.form.get('button')
            if button is not None:
                if button == 'next':
                    seats_in_vagon = request.form.get('seats_in_vagon')
                    session['new_vagons'].append([seats_in_vagon])
                    session['number_of_created_vagon'] += 1
                elif button == 'commit':
                    seats_in_vagon = request.form.get('seats_in_vagon')
                    session['new_vagons'].append([seats_in_vagon])
                    first_vagon = 1
                    for vagon in session['new_vagons']:
                        try:
                            cursor.execute(
                                'INSERT INTO vagon (vagon_number, train_id, vagon_number_of_seats) VALUES'
                                '(%s, %s, %s)',
                                (first_vagon,train_id, vagon[0]))
                            first_vagon += 1
                        except:
                            error = True
                        if not error:
                            conn.commit()
                    return redirect(url_for('about'))

        return render_template('create_new_vagons.html',
                               number_of_created_vagon=session['number_of_created_vagon'], error=error)


@main.route('/delete_train', methods=['GET', 'POST'])
def delete_train():
    if not session['isadmin']:
        redirect(url_for('home'))
    else:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('SELECT * from train')
        trains = cursor.fetchall()
        return render_template('delete_train.html', trains=trains)


@main.route('/delete_this_train/<int:train_id>', methods=['GET', 'POST'])
def delete_this_train(train_id):
    if not session['isadmin']:
        redirect(url_for('home'))
    else:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(
            "DELETE FROM ticket WHERE train_id = %s",
            (train_id,))
        cursor.execute(
            "DELETE FROM vagon WHERE train_id = %s",
            (train_id,))
        cursor.execute(
            "DELETE FROM train WHERE train_id = %s",
            (train_id,))
        conn.commit()
        return redirect(url_for('about'))


@main.route('/delete_route', methods=['GET', 'POST'])
def delete_route():
    if not session['isadmin']:
        redirect(url_for('home'))
    else:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('SELECT * from route')
        routes = cursor.fetchall()
        return render_template('delete_route.html', routes=routes)


@main.route('/delete_this_route/<int:route_id>', methods=['GET', 'POST'])
def delete_this_route(route_id):
    if not session['isadmin']:
        redirect(url_for('home'))
    else:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(
            "DELETE FROM station WHERE route_id = %s",
            (route_id,))
        cursor.execute(
            "SELECT train_id FROM train WHERE route_id = %s",
            (route_id,))
        trains_to_del = cursor.fetchall()
        for train in trains_to_del:
            cursor.execute(
                "DELETE FROM vagon WHERE train_id = %s",
                (train[0],))
            cursor.execute(
                "DELETE FROM ticket WHERE train_id = %s",
                (train[0],))
            cursor.execute(
                "DELETE FROM train WHERE train_id = %s",
                (train[0],))
        cursor.execute(
            "DELETE FROM route WHERE route_id = %s",
            (route_id,))
        return redirect(url_for('about'))


if __name__ == '__main__':
    main.run(debug=True)
