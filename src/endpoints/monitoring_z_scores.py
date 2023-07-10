from flask import jsonify, Blueprint

from connection_db.connection_db import config
from mysql.connector import connect

from utils import monitoring_rules
from utils.send_alert import send_alert

#This endpoint would be requested every full hour (e.g. 10:00:00 and not 10:20:00)
#FIRST SOLUTION - I AM USING AVERAGE RATES AND STANDARD DEVIATIONS AND Z-SCROES TO DETERMINE ANOMALIES

bp = Blueprint('monitoring_z_scores', __name__)

@bp.route("/monitoring/z-scores", methods=["GET"])
def monitoring_z_scores():
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
        send_alert({'alerts': alerts})

    cursor.close()
    connection.close()

    return jsonify(
        message = "Rate of each status in the last hour",
        data = response
    )