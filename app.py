""" write to a SQLite database with forms, templates
    add new record, delete a record, edit/update a record
    """

from flask import Flask, render_template, request, flash, send_file, make_response, jsonify, abort, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_login import login_required, LoginManager, login_user, UserMixin, logout_user, current_user

from flask_wtf import FlaskForm
from wtforms import SubmitField, SelectField, RadioField, HiddenField, StringField, IntegerField, FloatField, PasswordField

from wtforms.fields.html5 import DateField
from wtforms.validators import InputRequired, Optional, DataRequired

from datetime import date
import csv
import sqlite3
from io import StringIO, BytesIO
import os

import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
from plotly.offline import plot

DB_VAR=os.environ.get('DATABASE_URL', None)
OUT_DB_VAR=os.environ.get('EXTERNAL_DB', None)
GROUP_NAME=os.environ.get('GROUP_NAME', None)

app = Flask(__name__)

# Flask-WTF requires an enryption key - the string can be anything
app.config['SECRET_KEY'] = 'MLXH243GssUWwKdTWS7FDhdwYF56wPj8'

# Flask-Bootstrap requires this line
Bootstrap(app)

# the name of the database; add path if necessary

app.config['SQLALCHEMY_BINDS'] = {
    "db1":DB_VAR,
    "db2":OUT_DB_VAR}

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

###Login Setting###
login_manager = LoginManager() 
login_manager.init_app(app)
login_manager.login_view = 'login'
 
# this variable, db, will be used for all SQLAlchemy commands
db = SQLAlchemy(app)
    
# each table in the database needs a class to be created for it
# db.Model is required - don't change it
# identify all columns by name and data type
class Emissions(db.Model):
    __tablename__ = 'records'
    __bind_key__= "db1"
    id = db.Column(db.Integer, primary_key=True)
    kms = db.Column(db.Float)
    transport = db.Column(db.String)
    fuel = db.Column(db.String)
    date = db.Column(db.String)
    co2= db.Column(db.Float)
    ch4= db.Column(db.Float)
    user_name= db.Column(db.String)
    updated = db.Column(db.String)

    def __init__(self, kms, transport, fuel, date, co2, ch4, user_name, updated):
        self.kms = kms
        self.transport = transport
        self.fuel = fuel
        self.date = date
        self.co2 = co2
        self.ch4 = ch4
        self.user_name = user_name
        self.updated = updated    
        
engine_local = create_engine(DB_VAR)
engine_super =create_engine(OUT_DB_VAR)


### SupeUser DB
class SuperUser(UserMixin,db.Model):
    __tablename__ = 'users'
    __bind_key__= "db2"
    id = db.Column(db.Integer, primary_key=True)
    student = db.Column(db.String)
    user_name= db.Column(db.Integer)
    password = db.Column(db.String)
    group_name= db.Column(db.String)

    def __init__(self, user_name):
        self.user_name= user_name
        
####Everything is recorded. nothing removed        

class SuperBackUp(db.Model):
    __tablename__= 'backup'
    __bind_key__="db2"
    
    id = db.Column(db.Integer, primary_key=True)
    kms = db.Column(db.Float)
    transport = db.Column(db.String)
    fuel = db.Column(db.String)
    date = db.Column(db.String)
    co2= db.Column(db.Float)
    ch4= db.Column(db.Float)
    user_name= db.Column(db.String)
    updated = db.Column(db.String)
    
    def __init__(self, kms, transport, fuel, date, co2, ch4, user_name, updated):
        self.kms = kms
        self.transport = transport
        self.fuel = fuel
        self.date = date
        self.co2 = co2
        self.ch4 = ch4
        self.user_name = user_name
        self.updated = updated
        
###Global DB dynamically updated from sessions.
    
class SuperGlobal(db.Model):
    __tablename__= 'global'
    __bind_key__="db2"
    
    id = db.Column(db.Integer, primary_key=True)
    kms = db.Column(db.Float)
    transport = db.Column(db.String)
    fuel = db.Column(db.String)
    date = db.Column(db.String)
    co2= db.Column(db.Float)
    ch4= db.Column(db.Float)
    user_name= db.Column(db.String)
    updated = db.Column(db.String)
    group_name = db.Column(db.String)
    
    def __init__(self, kms, transport, fuel, date, co2, ch4, user_name, updated, group_name): 
        self.kms = kms
        self.transport = transport
        self.fuel = fuel
        self.date = date
        self.co2 = co2
        self.ch4 = ch4
        self.user_name = user_name
        self.updated = updated
        self.group_name = group_name  
 
@app.before_first_request
def before_first_request():
    db.create_all()
# +++++++++++++++++++++++
# forms with Flask-WTF

class LoginRecord(FlaskForm):
    user= StringField("User",validators=[InputRequired()])
    
    password = PasswordField('Password', validators=[DataRequired()])
        
    submit = SubmitField("Submit")
    
    
# form for add_record and edit_or_delete
# each field includes validation requirements and messages
class AddRecord(FlaskForm):
  id_field = HiddenField()
  ##Transport
  kms = FloatField("Kilometers",[InputRequired()])
  transport_type = SelectField("Type of Transport",
                                [InputRequired()],
                                choices=[
                                        ('Bus', 'Bus'),
                                        ('Car', 'Car'),
                                        ('Plane', 'Plane'),
                                        ('Ferry', 'Ferry'),
                                        ('Scooter', 'E-Scooter'),
                                        ('Bicycle', 'Bicycle'),
                                        ('Motorbike',"Motorbike"),
                                        ('Walk', 'Walk')
                                    ])
  

  fuel_type = SelectField("Fuel Type",
                           validators=[InputRequired()],choices=[])
  
  date=DateField("Date",[InputRequired()])
  

  gas =FloatField("kg/passenger km",[Optional()],description='Add CO2 kg/passenger km if known. \
                  Otherwise, leave blank and a default corresponding to the fuel \
                 type and vehicle average from "UK Government GHG Conversion Factors for Company Reporting" will be used')
  
  submit = SubmitField("Submit")

##Emissions factor per transport in kg per passemger km
##++++++++++++++++++++++
efco2={"Bus":{"Diesel":0.10231,"CNG":0.08,"Petrol":0.10231,"No Fossil Fuel":0},
       "Car":{"Hybrid":0.10567,"Petrol":0.18592,"Diesel":0.16453,"No Fossil Fuel":0},
       "Plane":{"Jet Fuel":0.24298,"No Fossil Fuel":0},
       "Ferry":{"Diesel":0.11131,"HFO":0.1131,"No Fossil Fuel":0},
       "Motorbike":{"Petrol":0.09816,"No Fossil Fuel":0},
       "Scooter":{"No Fossil Fuel":0},
       "Bicycle":{"No Fossil Fuel":0},
       "Walk":{"No Fossil Fuel":0}}

efch4={"Bus":{"Diesel":2e-5,"CNG":2.5e-3,"Petrol":2e-5,"No Fossil Fuel":0},
       "Car":{"Hybrid":1.5e-4,"Petrol":3.1e-4,"Diesel":3e-6,"No Fossil Fuel":0},
       "Plane":{"Jet Fuel":1.1e-4,"No Fossil Fuel":0},
       "Ferry":{"DO":3e-5,"HFO":3e-5,"No Fossil Fuel":0},
       "Motorbike":{"Petrol":2.1e-3,"No Fossil Fuel":0},
       "Scooter":{"No Fossil Fuel":0},
       "Bicycle":{"No Fossil Fuel":0},
       "Walk":{"No Fossil Fuel":0}}

#+++++++++++++++++++++++

# small form
class DeleteForm(FlaskForm):
    id_field = HiddenField()
    purpose = HiddenField()
    submit = SubmitField('Delete This Record')


# +++++++++++++++++++++++
# get local date - does not account for time zone
# note: date was imported at top of script
def stringdate():
    today = date.today()
    date_list = str(today).split('-')
    # build string in format 01-01-2000
    date_string = date_list[0] + "-" + date_list[1] + "-" + date_list[2]
    return date_string

###routes
@login_manager.user_loader
def load_user(user_id):
    return SuperUser(user_id)

@app.route('/login',methods=['GET', 'POST'])
def login():
    formlog=LoginRecord(request.form)
    
    if request.method =="POST" and formlog.validate_on_submit():
        ##check user. Add descendent to have record specific for the groupo first O.W admin record first
        user=SuperUser.query.filter_by(user_name=formlog.user.data).order_by(SuperUser.id.desc()).first()
        
        if user and formlog.password.data == user.password and GROUP_NAME==user.group_name:
            login_user(user)
            session.pop('_flashes', None) 
            return (redirect(url_for("index")))
        else:
        # if password is in correct , redirect to login page
            message = "User or password incorrect "
            
            return render_template('login.html', formlog=formlog, message=message)
            
    return render_template('login.html', formlog = formlog)


@app.route('/')
@login_required
def index():
    # get a list of unique values in the style column
    user_rec=SuperUser.query.filter_by(id=current_user.user_name).first().student
    transport = Emissions.query.with_entities(Emissions.transport).distinct()
    
    ###Outer Plot
    global_emissions=pd.read_sql("SELECT * FROM global",engine_super)
    global_emissions["date"]= pd.to_datetime(global_emissions["date"],yearfirst=True)
    global_emissions=global_emissions.sort_values(by="date")
    global_emissions=global_emissions.groupby(["date","group_name"]).agg({"co2":sum})
    global_emissions=global_emissions.reset_index()
    
    if global_emissions.shape[0]!=0:
        global_emissions["date"]=global_emissions["date"].dt.strftime('%Y-%m-%d %H:%M:%S')
        fig_global = px.line(global_emissions, x="date", y="co2", color='group_name',
                            labels={
                     "co2": "CO2 kg/passenger km",
                     "date": "Date",
                     "group_name": "Group Name"
                 },
                              title="Emissions per Group")
        
        fig_global.update_traces(mode='markers+lines')
        
        plot_div_global = plot(fig_global, output_type='div', include_plotlyjs=False)
    
    else:
        plot_div_global = ""
    if transport.first() is not None: ##To avoid crash when DB is empty
        ##Inner plot group
        group_emissions=pd.read_sql("SELECT * FROM records",engine_local)
        group_emissions["date"]= pd.to_datetime(group_emissions["date"],yearfirst=True)
        group_emissions=group_emissions.sort_values(by="date")
        group_emissions=group_emissions.groupby(["date","user_name"]).agg({"co2":sum})
        group_emissions=group_emissions.reset_index()
        group_emissions["date"]=group_emissions["date"].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        fig = px.line(group_emissions, x="date", y="co2", color='user_name', 
                      labels={
                     "co2": "CO2 kg/passenger km",
                     "date": "Date",
                     "user_name": "Name"
                 },
                     title="Emissions per Group Member")
        fig.update_traces(mode='markers+lines')
        plot_div = plot(fig, output_type='div', include_plotlyjs=False)
    
    
        return render_template('index.html',transport=transport,user_rec=user_rec,plot_div=plot_div,
                               plot_div_global=plot_div_global)
    
    else:
        return render_template('index.html',transport=transport,user_rec=user_rec, plot_div_global=plot_div_global)


@app.route('/inventory/<transport>')
def inventory(transport):
    emissions = Emissions.query.filter_by(transport=transport).order_by(Emissions.date).all()
    return render_template('list.html', emissions=emissions, transport=transport)

@app.route('/inventory')
def inventory_all():
    emissions = Emissions.query.order_by(Emissions.date).all()
    return render_template('list.html', emissions=emissions)

##New record
@app.route('/add_record', methods=['GET', 'POST'])
def add_record():
    form1 = AddRecord()
    form1.fuel_type.choices=[(fuel,fuel) for fuel in efco2["Bus"].keys()]
    if form1.validate_on_submit():
        kms = request.form['kms']
        transport = request.form['transport_type']
        fuel = request.form['fuel_type']
        date = request.form['date']
        # get today's date from function, above all the routes
        updated = stringdate()
        
        gas=request.form["gas"]
        
        if gas=="":     
            co2=float(kms)*efco2[transport][fuel]
            ch4=float(kms)*efch4[transport][fuel]
        else:
            co2=float(kms)*float(gas) 
            ch4=float(kms)*efch4[transport][fuel]
            
        user=SuperUser.query.filter_by(id=current_user.user_name).first()
        
        user_rec=user.student
        group_rec=user.group_name
        
        # the data to be inserted into Emission model - the table, records
        record = Emissions(kms, transport, fuel, date, co2, ch4, user_rec, updated)
        
        backup= SuperBackUp(kms, transport, fuel, date, co2, ch4, user_rec, updated)
        
        global_db= SuperGlobal(kms, transport, fuel, date, co2, ch4, user_rec, updated, group_rec)
        
        # Flask-SQLAlchemy magic adds record to database
        db.session.add(record)
        db.session.add(backup)
        db.session.add(global_db)
        
        db.session.commit()
        # create a message to send to the template
        message = f"The record for {transport} on {date} has been submitted."
        return render_template('add_record.html', message=message)
    else:
        # show validaton errors
        for field, errors in form1.errors.items():
            for error in errors:
                flash("Error in {}: {}".format(
                    getattr(form1, field).label.text,
                    error
                ), 'error')
        return render_template('add_record.html', form1=form1)
  
@app.route('/fuel_type/<transport>')
def fuel_type(transport):
    Allfuel=efco2[transport].keys()
    
    fuelArray= []
    
    for fuel in Allfuel:
        fuelObj={}
        fuelObj["transport"]=transport
        fuelObj["fuel"]=fuel
        fuelArray.append(fuelObj)
    
    return jsonify({"fuel_json": fuelArray})
        
        
#select a record to edit or delete
@app.route('/select_record')
def select_record():
    emissions = Emissions.query.order_by(Emissions.date).all()
    return render_template('select_record.html', emissions=emissions)    

# edit or delete - come here from form in /select_record
@app.route('/edit_or_delete', methods=['POST'])
def edit_or_delete():
    id = request.form['id']
    choice = request.form['choice']
    emissions = Emissions.query.filter(Emissions.id == id).first()
    # two forms in this template
    form1 = AddRecord()
    form1.fuel_type.choices=[(fuel,fuel) for fuel in efco2[emissions.transport].keys()]
    form2 = DeleteForm()
    return render_template('edit_or_delete.html', emissions=emissions, form1=form1, form2=form2, choice=choice)

# result of delete - this function deletes the record
@app.route('/delete_result', methods=['POST'])
def delete_result():
    id = request.form['id_field']
    purpose = request.form['purpose']
    emissions = Emissions.query.filter(Emissions.id == id).first()
    emissions_global= SuperGlobal.query.filter(SuperGlobal.kms==emissions.kms,
                                              SuperGlobal.transport==emissions.transport,
                                              SuperGlobal.fuel==emissions.fuel,
                                              SuperGlobal.date==emissions.date,
                                              SuperGlobal.updated==emissions.updated).first()
    
    if purpose == 'delete':
        db.session.delete(emissions)
        db.session.delete(emissions_global)
        db.session.commit()
        message = f"The record {emissions.transport} on {emissions.date} has been deleted from the database."
        return render_template('result.html', message=message)
    else:
        # this calls an error handler
        abort(405)

# result of edit - this function updates the record
@app.route('/edit_result', methods=['POST'])
def edit_result():
    id_in = request.form['id_field']
    # call up the record from the database
    emissions = Emissions.query.filter(Emissions.id == id_in).first()
    emissions_global= SuperGlobal.query.filter(SuperGlobal.kms==emissions.kms,
                                              SuperGlobal.transport==emissions.transport,
                                              SuperGlobal.fuel==emissions.fuel,
                                              SuperGlobal.date==emissions.date,
                                              SuperGlobal.updated==emissions.updated).first()
    # update all values
    emissions.kms = request.form['kms']
    emissions.transport = request.form['transport_type']
    emissions.fuel = request.form['fuel_type']
    emissions.date=request.form['date']
    # get today's date from function, above all the routes
    emissions.updated = stringdate()
     
    emissions.gas=request.form["gas"]
        
    # update all values
    emissions_global.kms = request.form['kms']
    emissions_global.transport = request.form['transport_type']
    emissions_global.fuel = request.form['fuel_type']
    emissions_global.date=request.form['date']
    # get today's date from function, above all the routes
    emissions_global.updated = stringdate()
     
    emissions_global.gas=request.form["gas"]
    
    if emissions.gas=="":     
        emissions.co2=float(emissions.kms)*efco2[emissions.transport][emissions.fuel]
        emissions.ch4=float(emissions.kms)*efch4[emissions.transport][emissions.fuel]
        
        emissions_global.co2=float(emissions_global.kms)*efco2[emissions_global.transport][emissions_global.fuel]
        emissions_global.ch4=float(emissions_global.kms)*efch4[emissions_global.transport][emissions_global.fuel]
    else:
        emissions.co2=float(emissions.kms)*float(emissions.gas)
        emissions.ch4=float(emissions.kms)*efch4[emissions.transport][emissions.fuel]
        
        emissions_global.co2=float(emissions_global.kms)*float(emissions_global.gas)
        emissions_global.ch4=float(emissions_global.kms)*efch4[emissions_global.transport][emissions_global.fuel]
            
    emissions.user=SuperUser.query.filter_by(id=current_user.user_name).first().user_name
    form1 = AddRecord()
    form1.fuel_type.choices=[(fuel,fuel) for fuel in efco2[emissions.transport].keys()]
    if form1.validate_on_submit():
        # update database record
        db.session.commit()
        # create a message to send to the template
        message = f"The data for {emissions.transport} on {emissions.date} has been updated."
        return render_template('result.html', message=message)
    else:
        # show validaton errors
        emissions.id = id_in
        for field, errors in form1.errors.items():
            for error in errors:
                flash("Error in {}: {}".format(
                    getattr(form1, field).label.text,
                    error
                ), 'error')
        return render_template('edit_or_delete.html', form1=form1, emissions=emissions, choice='edit')

##Download option
@app.route("/download")
def download():
    si = StringIO()
    
    outcsv=csv.writer(si)
    
    con=engine_local.connect()
    
    result= con.execute('select * from records')
    
    outcsv.writerow(x for x in result._metadata.keys)
    # dump rows
    outcsv.writerows(row for row in result)
    
    mem = BytesIO()
    mem.write(si.getvalue().encode('utf-8'))
    mem.seek(0)
    si.close()

    output = send_file(mem,mimetype="text/csv",
                       attachment_filename= 'emissions.csv',as_attachment=True, cache_timeout=0)
    
    return output
    
    con.close()
    os.remove('emissions.csv')
    
@app.route('/logout/')
@login_required
def logout(methods=["GET"]):
    user=current_user
    user.authenticated=False
    logout_user()
    engine_local.dispose()
    # redirecting to home page
    return redirect(url_for('login'))    
# +++++++++++++++++++++++
# error routes

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', pagetitle="404 Error - Page Not Found", pageheading="Page not found (Error 404)", error=e), 404

@app.errorhandler(405)
def form_not_posted(e):
    return render_template('error.html', pagetitle="405 Error - Form Not Submitted", pageheading="The form was not submitted (Error 405)", error=e), 405

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', pagetitle="500 Error - Internal Server Error", pageheading="Internal server error (500)", error=e), 500

# +++++++++++++++++++++++

if __name__ == '__main__':
    app.run(debug=True)
