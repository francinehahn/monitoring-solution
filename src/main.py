from flask import Flask, jsonify, request
from connection_db.connection_db import config
from datetime import datetime, timedelta
import utils.monitoring_rules as monitoring_rules
from mysql.connector import connect
from utils.send_alert import send_alert

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeRegressor

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
#FIRST SOLUTION - I AM USING AVERAGE RATES AND STANDARD DEVIATIONS AND Z-SCROES TO DETERMINE ANOMALIES
@app.route("/monitoring/z-scores", methods=["GET"])
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
    
    if z_score_failed > monitoring_rules.z_score_threshold_failed:
        alerts.append(f"ALERT! Failed transactions per hour are above normal - The z-score is {z_score_failed}")
    if z_score_denied > monitoring_rules.z_score_threshold_denied:
        alerts.append(f"ALERT! Denied transactions per hour are above normal - The z-score is {z_score_denied}")
    if z_score_reversed > monitoring_rules.z_score_threshold_reversed:
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
#SECOND SOLUTION - I AM USING A DECISION TREE TO DETERMINE ANOMALIES
@app.route("/monitoring/decision-tree", methods=["GET"])
def decision_tree():
    connection = connect(**config)
    cursor = connection.cursor()

    now = datetime.now()
    time = now.strftime("%H")

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

    data = pd.read_csv('files/transactions_hour.csv')

    X = data['time'].values.reshape(-1, 1)

    y_denied = data['denied'].values
    y_reversed = data['reversed'].values
    y_failed = data['failed'].values

    X_train, X_test, y_denied_train, y_denied_test, y_reversed_train, y_reversed_test, y_failed_train, y_failed_test = train_test_split(X, y_denied, y_reversed, y_failed, test_size=0.2, random_state=42)

    # Decision tree model: denied transactions
    model_denied = DecisionTreeRegressor(max_depth=5, min_samples_split=5, min_samples_leaf=2)
    model_denied.fit(X_train, y_denied_train)

    # Decision tree model: reversed transactions
    model_reversed = DecisionTreeRegressor(max_depth=5, min_samples_split=5, min_samples_leaf=2)
    model_reversed.fit(X_train, y_reversed_train)

    # Decision tree model: failed transactions
    model_failed = DecisionTreeRegressor(max_depth=5, min_samples_split=5, min_samples_leaf=2)
    model_failed.fit(X_train, y_failed_train)

    # Tests
    test_predict_denied = model_denied.predict(X_test)
    test_predict_reversed = model_reversed.predict(X_test)
    test_predict_failed = model_failed.predict(X_test)

    # Comparing the predictions with the real values
    for i in range(len(test_predict_denied)):
        print(f"Horário: {X_test[i]}, Valor real (denied): {y_denied_test[i]}, Previsão (denied): {test_predict_denied[i]}")
        print(f"Horário: {X_test[i]}, Valor real (reversed): {y_reversed_test[i]}, Previsão (reversed): {test_predict_reversed[i]}")
        print(f"Horário: {X_test[i]}, Valor real (failed): {y_failed_test[i]}, Previsão (failed): {test_predict_failed[i]}")
        
        if y_denied_test[i] - test_predict_denied[i] > monitoring_rules.decision_tree_threshold_denied * test_predict_denied[i]:
            print(f"ALERT! Denied rates are above normal - Expected rate: {test_predict_denied[i]}, Observed rate: {y_denied_test[i]}!")
        if y_reversed_test[i] - test_predict_reversed[i] > monitoring_rules.decision_tree_threshold_reversed * test_predict_reversed[i]:
            print(f"ALERT! Reversed rates are above normal - Expected rate: {test_predict_reversed[i]}, Observed rate: {y_reversed_test[i]}")
        if y_failed_test[i] - test_predict_failed[i] > monitoring_rules.decision_tree_threshold_failed * test_predict_failed[i]:
            print(f"ALERT! Failed rates are above normal - Expected rate: {test_predict_failed[i]}, Observed rate: {y_failed_test[i]}")

    # Predictions for the time this endpoint is requested
    predict_denied = model_denied.predict([[time]])
    predict_reversed = model_reversed.predict([[time]])
    predict_failed = model_failed.predict([[time]])

    #alerts
    alerts = []

    for rate in response:
        if rate['status'] == "failed" and rate['rate'] - round(predict_failed[0], 4) > monitoring_rules.decision_tree_threshold_failed * round(predict_failed[0], 3):
            alerts.append(f"ALERT! Failed rates are above normal - Expected rate: {predict_failed[0]}, Observed rate: {rate['rate']}!")
        if rate['status'] == "denied" and rate['rate'] - round(predict_denied[0], 3) > monitoring_rules.decision_tree_threshold_denied * round(predict_denied[0], 3):
            alerts.append(f"ALERT! Denied rates are above normal - Expected rate: {predict_denied[0]}, Observed rate: {rate['rate']}")
        if rate['status'] == "reversed" and rate['rate'] - round(predict_reversed[0], 3) > monitoring_rules.decision_tree_threshold_reversed * round(predict_reversed[0], 3):
            alerts.append(f"ALERT! Reversed rates are above normal - Expected rate: {predict_reversed[0]}, Observed rate: {rate['rate']}")
   
    #send email to the team
    if len(alerts) > 0:
        print(alerts)
        send_alert(app, {'alerts': alerts})

    cursor.close()
    connection.close()

    return jsonify(
        message = "Rate of each status in the last hour",
        data = response
    )




if __name__ == "__main__":
    app.run()
