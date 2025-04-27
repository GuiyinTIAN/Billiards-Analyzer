from openai import OpenAI
import json
import sys
import os

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)

json_file_path = 'billiard_analysis.json'
absolute_path = os.path.abspath(json_file_path)
print(f"Reading the file: {absolute_path}")


with open(json_file_path, 'r', encoding='utf-8') as file:
    data = json.load(file)

# xtract key information for constructing prompts
table_state = json.dumps(data['table_state'], indent=2)
balls_analysis = json.dumps(data['balls_analysis'], indent=2)
key_rule = data['system_context']['rules']
# print(key_rule)

prompt = f"The current status of the table in the American 9-ball game is as follows:{table_state}.The distribution information of the balls is as follows：{balls_analysis}.Please follow the rules strictly: '{key_rule}'. Give me some suggestions for hitting the ball. Give a summary after all the analysis."

# you need to set your own API key here.
APIKEY = "<YOUR_API_KEY>"

try:
    # for backward compatibility, you can still use `https://api.deepseek.com/v1` as `base_url`.
    client = OpenAI(api_key=APIKEY, base_url="https://api.deepseek.com/v1")

    response = client.chat.completions.create(
        # model="deepseek-reasoner",
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": data['system_context']['role']},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1024,
        temperature=0.7,
    )

    content = response.choices[0].message.content
    analysis_result_path = "analysis_result.txt"
    absolute_analysis_result_path = os.path.abspath(analysis_result_path)
    print(f"Reading Analyze Result: {absolute_analysis_result_path}")
    with open("analysis_result.txt", "w", encoding="utf-8") as f:
        f.write(content)
    # print(content)
    
except Exception as e:
    print(f"API fail to use: {str(e)}")
    with open("analysis_result.txt", "w", encoding="utf-8") as f:
        f.write(f"Failure to Analyze: {str(e)}")