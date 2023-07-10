from flask_mail import Message
from flask_mail import Mail
from flask import current_app

def send_alert(alerts):
    mail = Mail(current_app)
    msg = Message('ALERT! - Something is off', sender='fran_hahn@hotmail.com', recipients=['hahnf91@gmail.com'])
    msg.body = '\n'.join(alerts['alerts'])
    mail.send(msg)