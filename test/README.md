```
python -m venv test/env
source test/env/bin/activate
pip install -r lambda/requirements.txt
pip install python-lambda-local
source test/setenv.sh
python-lambda-local -f lambda_handler lambda/shopify_inventory.py test/event.json -t 10
python test/send_message.py 1
```
