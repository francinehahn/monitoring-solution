from flask import Flask
from endpoints.insert_transactions_per_minute import bp as bp_insert_transactions
from endpoints.monitoring_z_scores import bp as bp_z_scores
from endpoints.monitoring_decision_tree import bp as bp_decision_tree

from dotenv import load_dotenv, find_dotenv
import os

load_dotenv(find_dotenv())

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = 587  # SMTP port
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

#This endpoint would be requested every minute
app.register_blueprint(bp_insert_transactions)

#This endpoint would be requested every full hour (e.g. 10:00:00 and not 10:20:00)
#FIRST SOLUTION - I AM USING AVERAGE RATES AND STANDARD DEVIATIONS AND Z-SCROES TO DETERMINE ANOMALIES
app.register_blueprint(bp_z_scores)

#This endpoint would be requested every full hour (e.g. 10:00:00 and not 10:20:00)
#SECOND SOLUTION - I AM USING A DECISION TREE TO DETERMINE ANOMALIES
app.register_blueprint(bp_decision_tree)


if __name__ == "__main__":
    app.run()
