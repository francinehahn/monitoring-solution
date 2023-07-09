from flask_mail import Message
from flask_mail import Mail

def send_alert(app, alerts):
    mail = Mail(app)
    msg = Message('ALERT! - Something is off', sender='fran_hahn@hotmail.com', recipients=['hahnf91@gmail.com'])
    msg.body = '\n'.join(alerts['alerts'])
    mail.send(msg)