import datetime
import json
import os
import secrets
import sys
import time
from decimal import Decimal

import jwt
import modal
import requests
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv

load_dotenv()
stub = modal.Stub("coinbase-dca")
image = modal.Image.debian_slim().pip_install_from_requirements("requirements.txt")

def build_jwt(service, uri):
  """Builds JWTs for Coinbase Advanced Trading APIs using the private API key."""
  private_key_bytes = os.environ["COINBASE_PRIVATE_KEY"].encode('utf-8')
  private_key = serialization.load_pem_private_key(private_key_bytes, password=None)
  jwt_payload = {
    'sub': os.environ["COINBASE_KEY_NAME"],
    'iss': "coinbase-cloud",
    'nbf': int(time.time()),
    'exp': int(time.time()) + 60,
    'aud': [service],
    'uri': uri,
  }
  jwt_token = jwt.encode(
    jwt_payload,
    private_key,
    algorithm='ES256',
    headers={'kid': os.environ["COINBASE_KEY_NAME"], 'nonce': secrets.token_hex()},
  )
  return jwt_token

def coinbase_request(method, uri, body):
  """Wraps all requests to Coinbase APIs and injects the appropriate JWT"""
  jwt = build_jwt("retail_rest_api_proxy", f"{method} {uri}")
  resp = requests.request(
    method, 
    f"https://{uri}",
    params=body if method == "GET" else None,
    json=body if method == "POST" else None, 
    headers={
      "Content-Type": "application/json",
      "Authorization": f"Bearer {jwt}",
    }
  )
  return resp

def coinbase_get(uri, body=None):
  if body is None:
    body = {}
  return coinbase_request("GET", uri, body)

def coinbase_post(uri, body=None):
  if body is None:
    body = {}
  return coinbase_request("POST", uri, body)

def convert_usdc(amount):
  """
  Converts USDC into USD for trading purposes. This is a fee free transaction.
  Coinbase APIs require you to first get a quote and then commit the quote.
  """
  resp = coinbase_post("api.coinbase.com/api/v3/brokerage/convert/quote", body={
    "from_account": "USDC",
    "to_account": "USD",
    "amount": str(amount),
  })
  trade_id = resp.json()["trade"]["id"]

  resp = coinbase_post(f"api.coinbase.com/api/v3/brokerage/convert/trade/{trade_id}", body={
    "from_account": "USDC",
    "to_account": "USD",
  })

def get_latest_quote(asset):
  """Gets the latest quote for asset price by looking for the lowest ask"""
  market = f"{asset}-USD"
  resp = coinbase_get("api.coinbase.com/api/v3/brokerage/best_bid_ask", {
    "product_ids": [market]
  })
  data = next(datum for datum in resp.json()["pricebooks"] if datum["product_id"] == market)
  return float(data["asks"][0]["price"])

def get_asset_info(asset):
  """Gets the precision and minimum purchase info for an asset."""
  market = f"{asset}-USD"
  resp = coinbase_get(f"api.coinbase.com/api/v3/brokerage/products/{market}", {})
  data = resp.json()
  return {
    # quote_precision refers to the precision of the asset price in USD,
    # e.g. 0.001 means you can specify limit prices to the 3rd decimal point.
    "quote_precision": Decimal(data["quote_increment"]),
    # base_precision refers to the precision of the asset purchase size,
    # e.g. 0.001 means you can specify the amount of asset to buy to the 3rd decimal point.
    "base_precision": Decimal(data["base_increment"]),
    # min_base_size is the minimum amount of the asset that can be purchased via APi.
    "min_base_size": Decimal(data["base_min_size"]),
  }

def round_to_precision(amt, precision):
  num_ticks = Decimal(amt) // precision
  return num_ticks * precision

def dca_for_asset(asset, budget, frequency, run_time):
  deadline = run_time + datetime.timedelta(hours=3)

  if run_time.timetuple().tm_yday % frequency != 0:
    print(f"Skipping {asset} because policy says to only purchase every {frequency} days")
    return
  market = f"{asset}-USD"
  asset_data = get_asset_info(asset)
  latest_quote = get_latest_quote(asset)
  # Slightly underball the highest bid to ensure we take advantage of the lower maker fee pricing.
  limit_price = round_to_precision(latest_quote * 0.9995, asset_data["quote_precision"])
  size = round_to_precision(budget / limit_price, asset_data["base_precision"])
  if size < asset_data["min_base_size"]:
    raise Exception(f"Purchase size of {size} {asset} is below minimum size of {asset_data['min_base_size']}")
  resp = coinbase_post("api.coinbase.com/api/v3/brokerage/orders", body={
    "client_order_id": f"{asset}-{run_time.isoformat()}",
    "product_id": market,
    "side": "BUY",
    "order_configuration": {
      "limit_limit_gtd": {
        # The API expects all numbers to be passed as string due to the precision requirements.
        "base_size": str(size),
        "limit_price": str(limit_price),
        "end_time": deadline.isoformat() + "Z",
        "post_only": True,
      }
    }
  })
  resp_json = resp.json()
  if not resp_json["success"]:
    raise Exception(f"Error placing order for {asset}, reason = {resp_json['error_response']['message']}. Full details: {resp_json}")
  order_details = resp_json["order_configuration"]["limit_limit_gtd"]
  print(f"Successfully placed order for {order_details['base_size']} {asset} @ ${order_details['limit_price']} (order ID = {resp_json['success_response']['order_id']})")

# DCA Bot runs at 3pm EST every day (8pm UTC)
@stub.function(image=image, secrets=[modal.Secret.from_name("coinbase"), modal.Secret.from_name("dca-policy")], schedule=modal.Cron("0 20 * * *"))
def dca(): 
  run_time = datetime.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
  try:
    DCA_POLICY = json.loads(os.environ["DCA_POLICY"])
  except json.decoder.JSONDecodeError as e:
    print("DCA_POLICY is malformed. Make sure you have pushed a valid JSON to Modal secrets. See the README for more.", file=sys.stderr)
    raise e

  # Figure out how many funds are needed for today's buy, since this amount varies by day based on DCA policies.
  funds_required = 0
  for policy in DCA_POLICY["policies"]:
    if run_time.timetuple().tm_yday % policy["frequency"] != 0:
      continue
    funds_required += policy["budget"]
  WORST_MAKER_FEE_RATE = 0.006
  # Include some extra funds to cover the transaction fees. 0.6% is the worst possible maker fee right now.
  convert_usdc(funds_required * (1 + WORST_MAKER_FEE_RATE))
  # Wait for USDC conversion to commit on Coinbase's end.
  time.sleep(10)
  
  for policy in DCA_POLICY["policies"]:
    try:
      print(f'attempting DCA for {policy["token"]}')
      dca_for_asset(policy["token"], policy["budget"], policy["frequency"], run_time)
    except Exception as e:
      print(e)
      continue

@stub.local_entrypoint()
def main():
  dca.remote()