import os
from flask import Flask, Response
import requests
import json
import pandas as pd

# create our Flask app
app = Flask(__name__)

def get_coingecko_data(token):
    base_url = "https://api.coingecko.com/api/v3/coins/"
    token_map = {
        'ETH': 'ethereum',
        'BNB': 'binancecoin',
        'ARB': 'arbitrum',
        'BTC': 'bitcoin',
        'SOL': 'solana'
    }
    
    token = token.upper()
    if token in token_map:
        url = f"{base_url}{token_map[token]}/market_chart?vs_currency=usd&days=1&interval=minute"
        return url
    else:
        raise ValueError("Unsupported token")

def calculate_nvt_ratio(market_cap, transaction_volume):
    return market_cap / transaction_volume if transaction_volume != 0 else float('inf')

@app.route("/predict/<string:token>")
def predict_price(token):
    try:
        # Fetch data from Coingecko
        url = get_coingecko_data(token)
    except ValueError as e:
        return Response(json.dumps({"error": str(e)}), status=400, mimetype='application/json')

    headers = {
        "accept": "application/json",
        "x-cg-demo-api-key": os.getenv("COINGECKO_API_KEY")  # Получение ключа из переменной окружения
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        df_prices = pd.DataFrame(data["prices"], columns=["date", "price"])
        df_market_caps = pd.DataFrame(data["market_caps"], columns=["date", "market_cap"])
        df_total_volumes = pd.DataFrame(data["total_volumes"], columns=["date", "transaction_volume"])
        
        df_prices["date"] = pd.to_datetime(df_prices["date"], unit='ms')
        df_market_caps["date"] = pd.to_datetime(df_market_caps["date"], unit='ms')
        df_total_volumes["date"] = pd.to_datetime(df_total_volumes["date"], unit='ms')
        
        df = pd.merge(pd.merge(df_prices, df_market_caps, on="date"), df_total_volumes, on="date")
        df["nvt_ratio"] = df.apply(lambda row: calculate_nvt_ratio(row["market_cap"], row["transaction_volume"]), axis=1)
    else:
        return Response(json.dumps({"error": f"Failed to retrieve data from the API: {response.text}"}), 
                        status=response.status_code, 
                        mimetype='application/json')

    recent_nvt_ratio = df["nvt_ratio"].values[-10:]
    recent_prices = df["price"].values[-10:]

    try:
        predicted_nvt = recent_nvt_ratio.mean()
        predicted_price = recent_prices.mean() / predicted_nvt if predicted_nvt != 0 else recent_prices.mean()
        result = {
            "token": token,
            "predicted_nvt_ratio": predicted_nvt,
            "predicted_price": predicted_price
        }
        return Response(json.dumps(result), status=200, mimetype='application/json')
    except Exception as e:
        return Response(json.dumps({"error": str(e)}), status=500, mimetype='application/json')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000)
