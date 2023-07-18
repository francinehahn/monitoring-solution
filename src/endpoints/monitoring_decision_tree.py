from datetime import datetime, timedelta
from flask import jsonify, Blueprint

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import mean_squared_error
import math

from mysql.connector import connect
from connection_db.connection_db import config

from utils import monitoring_rules
from utils.send_alert import send_alert

bp = Blueprint('monitoring_decision_tree', __name__)

"""
This endpoint would be requested every full hour (e.g. 10:00:00 and not 10:20:00)
SECOND SOLUTION - I AM USING A DECISION TREE TO DETERMINE ANOMALIES
"""
@bp.route("/monitoring/decision-tree", methods=["GET"])
def monitoring_decision_tree():
    try:
        connection = connect(**config)
        cursor = connection.cursor()

        now = datetime.now()
        previous_hour = now - timedelta(hours=1)
        time = previous_hour.strftime("%H")

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

        X_train, X_test, y_denied_train, y_denied_test, y_reversed_train, y_reversed_test, y_failed_train, y_failed_test = train_test_split(X, y_denied, y_reversed, y_failed, test_size=0.35, random_state=42)

        # Decision tree model: denied transactions
        model_denied = DecisionTreeRegressor(max_depth=4, min_samples_split=2, min_samples_leaf=3)
        model_denied.fit(X_train, y_denied_train)

        # Decision tree model: reversed transactions
        model_reversed = DecisionTreeRegressor(max_depth=4, min_samples_split=2, min_samples_leaf=3)
        model_reversed.fit(X_train, y_reversed_train)

        # Decision tree model: failed transactions
        model_failed = DecisionTreeRegressor(max_depth=3, min_samples_split=2, min_samples_leaf=3)
        model_failed.fit(X_train, y_failed_train)

        # Tests
        test_predict_denied = model_denied.predict(X_test)
        test_predict_reversed = model_reversed.predict(X_test)
        test_predict_failed = model_failed.predict(X_test)

        # Root Mean Squared Error (RMSE)
        mean_squared_error_denied = mean_squared_error(y_denied_test, test_predict_denied)
        print("RMSE denied transactions: ", math.sqrt(mean_squared_error_denied))

        mean_squared_error_reversed = mean_squared_error(y_reversed_test, test_predict_reversed)
        print("RMSE reversed transactions: ", math.sqrt(mean_squared_error_reversed))

        mean_squared_error_failed = mean_squared_error(y_failed_test, test_predict_failed)
        print("RMSE failed transactions: ", math.sqrt(mean_squared_error_failed))

        # Predictions for the previous hour when this endpoint is requested
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
            send_alert({'alerts': alerts})

        cursor.close()
        connection.close()

        return jsonify(
            message = "Rate of each status in the last hour",
            data = response
        )
    
    except Exception as err:
        response =  jsonify(
            message = f"Unexpected error: {err}"
        )
        response.status_code = 400
        return response