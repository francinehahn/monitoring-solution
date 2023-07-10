from flask import jsonify, request, Blueprint

from connection_db.connection_db import config
from mysql.connector import connect

from datetime import datetime, timedelta

#This endpoint would be requested every minute
bp = Blueprint('insert_transactions_per_minute', __name__)

@bp.route("/monitoring", methods=["POST"])
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