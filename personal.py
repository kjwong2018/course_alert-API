from flask import Flask, jsonify, request
from flask_restful import Resource, Api
from twilio.rest import Client
import courseconfig as config
import re, urllib, json, smtplib, psycopg2

app = Flask(__name__)
api = Api(app)

class courseSearch(Resource):
    #Search course function
    def get(self, course_id):
        if any(pre in course_id.upper() for pre in config.course_prefix):
            course_split = re.split('(\d+)',course_id)
            #Request course from school API
            api_url = config.url['baseurl'].replace("[dept]",course_split[0]).replace("[cnum]",course_split[1])
            api_data = urllib.urlopen(api_url)
            api_resp = api_data.read().decode('utf-8')
            api_json = json.loads(api_resp)
            if 'err' in api_json:
                return jsonify({'error':'Course not found'})
            #Construct new json with only data needed from api_json
            resp_json ={}
            for course in api_json['courses']:
                resp_json[course['section']] = {}
                resp_json[course['section']]['instructor'] = course['instructor']
                resp_json[course['section']]['room'] = course['room']
                resp_json[course['section']]['pattern'] = course['when'][0]['pattern']
                resp_json[course['section']]['start'] = course['when'][0]['dates']['start']
                resp_json[course['section']]['end'] = course['when'][0]['dates']['end']
                resp_json[course['section']]['seats'] = course['enrollment']['section'] - course['enrollment']['enrolled']
            return jsonify(resp_json)
        return jsonify({'error': 'Course not found'})

    #Register to be alert for course
    def post(self, course_id):
        '''
        Register to be alert for a specific course
        Post data should have {
                                "email" : "something",
                                "section" : "something"
                              }
        Email can be replace by "phone"
        '''
        rcvd = request.get_json()
        if "section" in rcvd:
            if "email" in rcvd:
                '''
                    You need a second email for this as one is sender one is receiver.
                    Sender's email needs to allow "Access for less secure apps" for python to send email (gmail) 
                '''
                try:
                    d = database(config.sql['database'], config.sql['user'], config.sql['pass'])
                    d.cur.execute("INSERT INTO coursez (email,course,section,) VALUES (%s,%s,%s)",(rcvd['email'],course_id,rcvd['section']))
                    d.conn.commit()
                    d.close()
                    print("Inserted email and course information into table")
                except psycopg2.Error as e:
                    if d.conn:
                        d.conn.rollback()
                        d.close()
                    print(e.pgcode)
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(config.email['id'], config.email['pass'])
                msg = 'Subject: [Test]Course Alert\n\n' + 'You are registered to be alerted for ' + course_id + ' ' + rcvd['section']
                server.sendmail(config.email['id'], rcvd["email"], msg)
                server.quit()
                return jsonify({'message': 'Registered succefully'})
            elif "phone" in rcvd:
                try:
                    d = database(config.sql['database'], config.sql['user'], config.sql['pass'])
                    d.cur.execute("INSERT INTO coursez (phone,course,section,) VALUES (%s,%s,%s)",(rcvd['phone'],course_id,rcvd['section']))
                    d.conn.commit()
                    d.close()
                    print("Inserted phone and course information into table")
                except psycopg2.Error as e:
                    if d.conn:
                        d.conn.rollback()
                        d.close()
                    print(e.pgcode)
                client = Client(config.twilio['sid'],config.twilio['token'])
                message = client.messages.create(
                    body='\nYou are registered to be alerted for\n'+ course_id + ' ' + rcvd['section'],
                    from_=config.twilio['phone'],
                    to='+1'+rcvd['phone']
                    #phone number can be modified for +1 or not depending on your input
                )
                return jsonify({'message': 'Registered succefully ' + message.sid})
            else:
                return jsonify({"error":"Improper data format for post. Missing email or phone?"})
        return jsonify({"error":"Improper data format for post. Missing section?"})

class database ():
    def __init__(self, db=None, user=None, passW=None):
        self.conn = psycopg2.connect(database=db, user=user, password=passW)
        self.cur = self.conn.cursor()
    '''
        Need a better execute function
        
        def execute(self, statement):
        try:
            self.cur.execute(statement)
            self.conn.commit()
        except psycopg2.Error as e:
            if self.conn:
                self.conn.rollback()
            print("Error code: " + e.pgcode)
            return "Error"
        return self.cur.fetchall() if "SELECT" in statement else "Complete"
    '''

    def close(self):
        self.conn.close()

api.add_resource(courseSearch,'/course/<course_id>')

try:
    d = database(config.sql['database'], config.sql['user'], config.sql['pass'])
    d.cur.execute("CREATE TABLE coursez(id SERIAL NOT NULL PRIMARY KEY, email TEXT, phone TEXT, course VARCHAR(7), section VARCHAR(3))")
    print('Created table "coursez" in PostgreSQL')
except psycopg2.Error as e:
    if d.conn:
        d.conn.rollback()
    print(e.pgcode)
d.conn.commit()
d.close()

if __name__ == '__main__':
    app.run()