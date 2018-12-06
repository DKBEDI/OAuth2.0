#finalProject.py
import sys; print sys.path
from flask import Flask, render_template, request, redirect, url_for, flash, json, jsonify

# import CRUD Operations
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Restaurant, MenuItem

app = Flask(__name__)

# NEW IMPORTS FOR ANTI FORGERY STATE TOKEN
from flask import session as login_session
import random, string

# GConnect IMPORTS inc. JSON formatted client stores (e.g. client ID & client secret) & catch autorisation code errors for token access
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
# COMPREHENSIVE HTTP MODULES
import httplib2
# PROVIDE AN API FOR CONVERTING IN MEMORY PYTHON OBJECTS TO A SERIALISED REP AKA JSON/JAVASCRIPT-OBJECT-NOTATION
import json
# CONVERT RETURN VALUES TO A REAL RESPONSE OBJECT THAT CAN BE SENT TO A CLIENT
from flask import make_response
# APACHE 2.0 LICENSED HTTP LIBRARY FOR PYTHON (SIMILAR TO URLLIB2)
import requests

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Restaurant Menu Application"

# Create session and connect to DB
#engine = create_engine('sqlite:///restaurantmenu.db')
engine = create_engine('sqlite:///restaurantmenu.db?check_same_thread=False')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

########################### TEST DATA START ###########################

#Fake Restaurants
#restaurant = {'name': 'The CRUDdy Crab', 'id': '1'}

#restaurants = ""
#restaurants = [{'name': 'The CRUDdy Crab', 'id': '1'}, {'name':'Blue Burgers', 'id':'2'},{'name':'Taco Hut', 'id':'3'}]

#Fake Menu Items
#items = ""
#items = [ {'name':'Cheese Pizza', 'description':'made with fresh cheese', 'price':'$5.99','course' :'Entree', 'id':'1'}, {'name':'Chocolate Cake','description':'made with Dutch Chocolate', 'price':'$3.99', 'course':'Dessert','id':'2'},{'name':'Caesar Salad', 'description':'with fresh organic vegetables','price':'$5.99', 'course':'Entree','id':'3'},{'name':'Iced Tea', 'description':'with lemon','price':'$.99', 'course':'Beverage','id':'4'},{'name':'Spinach Dip', 'description':'creamy dip with fresh spinach','price':'$1.99', 'course':'Appetizer','id':'5'} ]

#item =  {'name':'Cheese Pizza','description':'made with fresh cheese','price':'$5.99','course' :'Entree','id':'1','restaurant_id':'1'}

########################### TEST DATA END ###########################

#  i. CREATE A STATE TOKEN TO PREVENT REQUEST FORGERY.
# STORE IT IN THE SESSION FOR LATER VALIDATION
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(32))
    login_session['state'] = state
    #return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)

# ii. ACCEPT POST REQUESTS
@app.route('/gconnect', methods=['GET','POST'])
def gconnect():
    stateToken = request.args.get('state')
    print('request.args.get[state] : %s' % stateToken)
    print('login_session[state] : %s' % login_session['state'])
    if stateToken != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter'), 402)
        response.headers['Content-Type'] = 'application/json'
        return response
    code = request.data
    try:
        # UPGRADE THE AUTHORISATION CODE INTO A CREDENTIALS OBJECT
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps('Failed to upgrade the authorisation code.'), 403)
        response.headers['Content-Type'] = 'application/json'
        return response
    # CHECK IF THE ACCESS TOKEN IS VALID
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s' % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # IF THERE IS AN ERROR IN THE TOKEN ACCESS INFO, ABORT
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response
    # IS THE ACCESS TOKEN BEING USED BY THE INTENDED USER
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(json.dumps("Token's user ID doesn't match given user ID."), 404)
        response.headers['Content-Type'] = 'application/json'
        return response
    # IS THE ACCESS TOKEN VALID FOR THIS APP
    if result['issued_to'] != CLIENT_ID:
        response = make_response(json.dumps("Token's client ID does not match app's."), 405)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response
    # IS THE USER ALREADY LOGGED IN
    stored_access_token = login_session.get('access_token')
    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('User is already connected.'), 200)
        response.header['Content-Type'] = 'application/json'
        return response
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    
    # STORE THE ACCESS TOKEN IN THE SESSION FOR LATER USE
    login_session['access_token'] = credentials.access_token
    login_session['credentials'] = credentials
    login_session['gplus_id'] = gplus_id

    # GET USER INFO
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt':'json'}

    answer = request.get(userinfo_url, params=params)

    #data = json.loads(answer.text)
    data = answer.json()

    login_session['username'] = data["name"]
    login_session['picture'] = data["picture"]
    login_session['email'] = data["email"]

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output

#A. Make an API Endpoint for all restaurants
@app.route('/restaurants/JSON')
def allRestaurantsJSON():
    restaurants = session.query(Restaurant).all()
    return jsonify(listRestaurants = [r.serialize for r in restaurants])

#B. Make an API Endpoint to list menu items for a given restaurant
@app.route('/restaurant/<int:restaurant_id>/menu/JSON')
def allMenuItemsJSON(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    menuItems = session.query(MenuItem).filter_by(restaurant_id = restaurant.id).all()
    return jsonify(listMenuItems = [i.serialize for i in menuItems])

#C. Make an API Endpoint to list a specific menu item for a given restaurant
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/JSON')
def oneMenuItemJSON(restaurant_id, menu_id):
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    aMenuItem = session.query(MenuItem).filter_by(id = menu_id, restaurant_id = restaurant_id).one()
    return jsonify(oneMenuItem=[aMenuItem.serialize])

#1. SHOW ALL RESTAURANTS
@app.route('/')
@app.route('/restaurant/', methods=['GET'])
def showRestaurants():
    restaurants = session.query(Restaurant).all()
    #print(restaurants)
    if restaurants == []:
        flash("There are no restaurants")
    #return "<html><body>This page will show all my restaurants</html></body>"
    return render_template('restaurants.html', restaurants = restaurants)

#2. SHOW MENU ITEMS FOR A RESTAURANT
@app.route('/restaurant/<int:restaurant_id>/')
@app.route('/restaurant/<int:restaurant_id>/menu')
def showMenuItems(restaurant_id, methods=['GET','POST']):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    items = session.query(MenuItem).filter_by(restaurant_id = restaurant_id).all()
    #print(items)
    if items == []:
        flash("There are no menu items to display")
    #return "<html><body>This page will show all menu items for restaurant %s</html></body>" % restaurant_id
    return render_template('menu.html', restaurant=restaurant, items=items)

#3. CREATE A NEW RESTAURANT
@app.route('/restaurant/new', methods=['GET','POST'])
def newRestaurant():
    if request.method == 'POST':
        createRestaurant = Restaurant(name = request.form['name'])
        session.add(createRestaurant)
        session.commit()
        flash("Created new restaurant %s" % request.form['name'])
        return redirect(url_for('showRestaurants'))
    else:
        #return "<html><body>This page will be for making a new restaurant</html></body>"
        return render_template('newRestaurant.html')

#4. EDIT AN EXISTING RESTAURANT
@app.route('/restaurant/<int:restaurant_id>/edit', methods=['GET','POST'])
def editRestaurant(restaurant_id):
    editedRestaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if request.method == 'POST':
        if request.form['name']:
            editedRestaurant.name = request.form['name']
        session.add(editedRestaurant)
        session.commit()
        flash("Restaurant Details Have Been Updated")
        return redirect(url_for('showRestaurants'))
    else:
        #return "<html><body>This page will be for editing restaurant %s</html></body>" % restaurant_id
        return render_template('editRestaurant.html', restaurant_id=restaurant_id, r=editedRestaurant)

#5. DELETE AN EXISTING RESTAURANT
@app.route('/restaurant/<int:restaurant_id>/delete', methods=['GET','POST'])
def deleteRestaurant(restaurant_id):
    toDeleteRestaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    if request.method == 'POST':
        session.delete(toDeleteRestaurant)
        session.commit()
        flash("Restaurant %s has been removed" % toDeleteRestaurant.name)
        return redirect(url_for('showRestaurants'))
    else:
        #return "<html><body>This page will be for deleting restaurant %s</html></body>" % restaurant_id
        return render_template('deleteRestaurant.html', restaurant_id = restaurant_id)

#6. CREATE A NEW MENU ITEM FOR A RESTAURANT
@app.route('/restaurant/<int:restaurant_id>/menu/new', methods=['GET','POST'])
def newMenuItem(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    if request.method == 'POST':
       #print("WAIT FOR IT...")
        #print(request.form)
        newName = request.form['name']
        newDescription = request.form['description']
        newPrice = request.form['price']
        newCourse = request.form['course']
        newItem = MenuItem(name = newName, description = newDescription, price = newPrice, course = newCourse, restaurant_id = restaurant_id, restaurant = restaurant)
        session.add(newItem)
        session.commit()
        flash("Menu Item %s Has Been Added for %s" % (newItem.name, restaurant.name))
        return redirect(url_for('showMenuItems', restaurant_id=restaurant_id))
    else:
        #return "<html><body>This page will be for making a new menu item for restaurant %s</html></body>" % restaurant_id
        return render_template('newMenuItem.html', restaurant=restaurant, restaurant_id=restaurant_id)

#7. EDIT AN EXISTING MENU ITEM FOR A RESTAURANT
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/edit', methods=['GET','POST'])
def editMenuItem(restaurant_id, menu_id):
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    editedItem = session.query(MenuItem).filter_by(id = menu_id).one()
    if request.method == 'POST':
        if request.form['name']:
            editedName = request.form['name']
        if request.form['description']:
            editedDescription = request.form['description']
        if request.form['price']:
            editedPrice = request.form['price']
        if request.form['course']:
            editedCourse = request.form['course']
        editedItem = MenuItem(name = editedName, description = editedDescription, price = editedPrice, course = editedCourse, restaurant_id = restaurant_id, restaurant = restaurant, id = menu_id)
        session.merge(editedItem)#.where((restaurant_id = restaurant_id) and (id = menu_id))
        session.commit()
        flash("Menu Item Has Been Updated")
        return redirect(url_for('showMenuItems', restaurant_id=restaurant_id))
    else:
        #return "<html><body>This page will be for editing menu item %s for restaurant %s</html></body>" % (menu_id, restaurant_id)
        return render_template('editMenuItem.html', restaurant=restaurant, item=editedItem)

#8. DELETE AN EXISTING MENU ITEM FOR A RESTAURANT
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/delete', methods=['GET','POST'])
def deleteMenuItem(restaurant_id, menu_id):
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    deleteItem = session.query(MenuItem).filter_by(id = menu_id).one()
    if request.method == 'POST':
        session.delete(deleteItem)
        session.commit()
        flash("Menu Item %s Has Been Deleted" % deleteItem.name)
        return redirect(url_for('showMenuItems', restaurant_id = restaurant_id))
    else:
        #return "<html><body>This page will be for deleting menu item %s for restaurant %s</html></body>" % (menu_id, restaurant_id)
        return render_template('deleteMenuItem.html', restaurant=restaurant, item=deleteItem)

if __name__ == '__main__':
	app.secret_key = 'super_secret_key'
	app.debug = True
	app.run(host = '0.0.0.0', port = 5000)
