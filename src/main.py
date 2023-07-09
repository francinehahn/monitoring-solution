from flask import Flask, jsonify, request
from connection_db.connection_db import config
from datetime import datetime, timedelta
import utils.monitoring_rules as monitoring_rules
from mysql.connector import connect
from utils.send_alert import send_alert

import pandas as pd
from sklearn.linear_model import LinearRegression

from dotenv import load_dotenv, find_dotenv
import os

load_dotenv(find_dotenv())

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

#flask email
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = 587  # SMTP port
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")


#This endpoint would be requested every minute
@app.route("/monitoring", methods=["POST"])
def insert_transactions_per_minute():
    connection = connect(**config)
    cursor = connection.cursor()
    body = request.json

    try:        
        #I am pretending to have received data from a minute before
        now = datetime.now()
        now = now.replace(second=0)
        minute_before = (now - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:00")
        
        for transaction in body:
            if transaction['status'] != "approved" and transaction['status'] != "denied" and transaction['status'] != "reversed" and transaction['status'] != "processing" and transaction['status'] != "backend_reversed" and transaction['status'] != "refunded" and transaction['status'] != "failed":
                raise Exception("""The status of the transaction can only be 'approved', 'denied', 'reversed', 
                    'processing', 'backend_reversed', 'refunded', 'failed'""")
            
            if transaction['count'] <= 0:
                raise Exception("The quantity of each transaction status must be higher than 0.")
            
            cursor.execute(
                f"""INSERT INTO transactions (time, status, count) 
                VALUES ('{minute_before}', '{transaction['status']}', {transaction['count']})"""
            )
            connection.commit()

        response = jsonify(
            message = "The transaction information has been successfully registered.",
            data = body
        )
        response.status_code = 201
        return response
    
    except Exception as err:
        response =  jsonify(
            message = f"Unexpected error: {err}"
        )
        response.status_code = 400
        return response
    finally:
        cursor.close()
        connection.close()
    


#This endpoint would be requested every full hour (e.g. 10:00:00 and not 10:20:00)
@app.route("/monitoring/rates-per-hour", methods=["GET"])
def get_transactions_per_hour_and_alert():
    connection = connect(**config)
    cursor = connection.cursor()

    cursor.execute("""SELECT status,
        ROUND(SUM(count) / (SELECT SUM(count) FROM transactions WHERE time >= DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 HOUR), INTERVAL 1 HOUR)), 3) 
        AS rate
        FROM transactions 
        WHERE time >= DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 HOUR), INTERVAL 1 HOUR)
        GROUP BY status;"""
    )
    rate_per_hour = cursor.fetchall()
    
    response = []
    for rate in rate_per_hour:
        response.append({
            "status": rate[0],
            "rate": float(rate[1])
        })

    # calculate the z-score for each status
    z_score_failed = 0
    z_score_denied = 0
    z_score_reversed = 0

    for rate in response:
        if rate['status'] == "failed":
            z_score_failed = monitoring_rules.z_score_hour_failed(rate['rate'])
        if rate['status'] == "denied":
            z_score_denied = monitoring_rules.z_score_hour_denied(rate['rate'])
        if rate['status'] == "reversed":
            z_score_reversed = monitoring_rules.z_score_hour_reversed(rate['rate'])

    #alerts
    alerts = []
    
    if z_score_failed > monitoring_rules.z_score_positive_threshold:
        alerts.append(f"ALERT! Failed transactions per hour are above normal - The z-score is {z_score_failed}")
    if z_score_denied > monitoring_rules.z_score_positive_threshold:
        alerts.append(f"ALERT! Denied transactions per hour are above normal - The z-score is {z_score_denied}")
    if z_score_reversed > monitoring_rules.z_score_positive_threshold:
        alerts.append(f"ALERT! Reversed transactions per hour are above normal - The z-score is {z_score_reversed}")

    #The alert will only be triggered if at least one of the z-scores is higher than 3
    if len(alerts) > 0:
        print(alerts)
        send_alert(app, {'alerts': alerts})

    cursor.close()
    connection.close()

    return jsonify(
        message = "Rate of each status in the last hour",
        data = response
    )



#This endpoint would be requested every full hour (e.g. 10:00:00 and not 10:20:00)
@app.route("/monitoring/approved-transactions", methods=["GET"])
def get_approved_transactions_per_hour_and_alert():
    connection = connect(**config)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT DATE_FORMAT(time, '%Y-%m-%d %H:00:00') as time, SUM(count)
        FROM transactions
        WHERE status = "approved" AND time >= DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 HOUR), INTERVAL 1 HOUR)
        GROUP BY DATE_FORMAT(time, '%Y-%m-%d %H:00:00');
    """)
    approved_transactions_hour = cursor.fetchall()
    
    response = {
        "time": approved_transactions_hour[0][0],
        "count": int(approved_transactions_hour[0][1])
    }

    date_hour = datetime.strptime(response["time"], "%Y-%m-%d %H:%M:%S")
    hour = date_hour.hour

    # Loading the data
    data = pd.read_csv('files/approved_transactions_hour.csv')

    data['time'] = data['time'].astype(int)
    data = data.set_index('time')

    rolling_avg = data['count'].rolling(window=3, min_periods=1).mean().shift(-1)
    rolling_sd = data['count'].rolling(window=3, min_periods=1).std().shift(-1)

    avg_count = rolling_avg.loc[hour]
    sd_count = rolling_sd.loc[hour]
    
    z_score = monitoring_rules.z_score_hour_approved(response['count'], avg_count, sd_count)
    
    if z_score < monitoring_rules.z_score_negative_threshold:
        send_alert(app, {"alerts": [f"""ALERT! The number of approved transactions was below the expected
            for the past hour ({response['time']})! The expected count should have been around 
            {round(avg_count, 2)} +- {round(sd_count, 2)} but the observed count was {response['count']}.
            The z-score was at {z_score}."""]})

    return jsonify(
        message = "Number of approved transactions in the last hour",
        data = response
    )


if __name__ == "__main__":
    app.run()
