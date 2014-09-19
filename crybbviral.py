import os
import urllib
import cgi
import string
import random
import re

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.api import mail

import jinja2
import webapp2

#Third party libraries
import sys
lib_dir = "libs"
sys.path += [os.path.join(lib_dir, name) for name in os.listdir(lib_dir)
            if os.path.isdir(os.path.join(lib_dir, name))] #Add subdirectories of 'libs' to path
import facebook

def set_trace():
    import pdb, sys
    debugger = pdb.Pdb(stdin=sys.__stdin__, 
        stdout=sys.__stdout__)
    debugger.set_trace(sys._getframe().f_back)

################################################################################    
# Helper functions

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

class BlogHandler(webapp2.RequestHandler):

    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        return render_str(template, **params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)

def get_config():
    config = Configuration.get_by_id(1)
    if not config:
        config = Configuration(id=1, fb_id="", fb_secret="")
        config.put()
    return config

def get_facebook_id():
    return get_config().fb_id

def get_facebook_secret():
    return get_config().fb_secret
        
EMAIL_RE  = re.compile(r'^[\S]+@[\S]+\.[\S]+$')
def valid_email(email):
    return EMAIL_RE.match(email)
################################################################################
    
def welcomeEmail(user_email, user_ID):
    mail.send_mail(sender="Crybb <sam.pattuzzi@googlemail.com>",
              to="<"+user_email+">",
              subject="Thanks for Signing Up!",
              body="""
    Here at crybb, we like to reward sharing.
    
    Share the link below, and the more people who sign up through it, the earlier beta access you get!
    http://crybbviral.appspot.com/referral/"""+str(user_ID)+"""
    
    We will update you when your beta access is ready, but in the meantime find us on social media:
    http://www.facebook.com/wearecrybb
    http://www.twitter.com/wearecrybb
    
    Victoria,
    Founder, Crybb
    """
    )
        
def createUser (profile, user_location, user_refereeID):
    
    try:
        email = profile["email"]
    except KeyError:
        email = None
    newUser = User(
            id=str(profile["id"]),
            name=profile["name"],
            email=email,
            profile_url=profile["link"],
            location=user_location,
            refereeID=user_refereeID,
            clicks=0,
            signups=0,
            access_token=profile["access_token"],
            )
    newUser.put()
    
    if user_refereeID != "NULL":
        signupCount (user_refereeID)
    
    user_ID = newUser.key.id()
    if email:
        welcomeEmail(email, user_ID)
    
    return newUser

@ndb.transactional
def clickCount (uniqueID):
    referee=User.get_by_id(str(uniqueID))
    referee.clicks += 1
    referee.put()
    return referee.email

@ndb.transactional
def signupCount (uniqueID):
    referee=User.get_by_id(str(uniqueID))
    referee.signups += 1
    referee.put()
    return referee.email
    
def emailExists (email):
    temp = User.query().filter(ndb.GenericProperty('email') == email).get()
    if temp:
        return temp.key.id()
    else:
        return 0
    
class User(ndb.Model):
    email = ndb.StringProperty(required=False)
    location = ndb.StringProperty()
    refereeID = ndb.StringProperty()
    clicks = ndb.IntegerProperty()
    signups = ndb.IntegerProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)
    name = ndb.StringProperty(required=True)
    profile_url = ndb.StringProperty(required=True)
    access_token = ndb.StringProperty(required=True)

class Configuration(ndb.Model):
    fb_id = ndb.StringProperty()
    fb_secret = ndb.StringProperty()
    
class Landing(BlogHandler):
    def get(self): 

        self.render('landing.html', fb_app_id = get_facebook_id(), refereeID = 'NULL')     

class Progress(BlogHandler):
    def get(self):
        location = self.request.get('location', '')
        refereeID = self.request.get('refereeID', '')

        message = None
        currentUser = None

        cookie = facebook.get_user_from_cookie(
            self.request.cookies, get_facebook_id(), get_facebook_secret())

        graph = facebook.GraphAPI(cookie["access_token"])
        graph.extend_access_token(get_facebook_id(), get_facebook_secret())
        profile = graph.get_object("me")
        profile["access_token"] = graph.access_token
        print profile

        if cookie:
            # Store a local instance of the user data so we don't need
            # a round-trip to Facebook on every request
            currentUser = User.get_by_id(cookie["uid"])
            if not currentUser:
                if location:
                    currentUser = createUser(profile, location, refereeID)
                else:
                    message = "Invalid sign up. You didn't select a location."
            else:
                if currentUser.access_token != profile["access_token"]:
                    currentUser.access_token = profile["access_token"]
                if location:
                    currentUser.location = location
                currentUser.put()
        else:
            message = "You are not signed in to Facebook."
        
        self.render('progress.html', fb_app_id = get_facebook_id(), user = currentUser, message = message)       
        
class Referral(BlogHandler):
    def get(self,refereeID):
        
        clickCount(refereeID)
        
        self.render('landing.html', fb_app_id = get_facebook_id(), refereeID = refereeID)      

class WireFrame(BlogHandler):
    def get(self):
        self.render('wireframe.html')      

application = webapp2.WSGIApplication([
     webapp2.Route('/', handler=Landing),
     webapp2.Route('/progress', handler=Progress),
     webapp2.Route('/referral/<refereeID>', handler=Referral),
     webapp2.Route('/wireframe', handler=WireFrame),
     ], debug=True)
