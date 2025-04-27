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
print(f"正在读取文件: {absolute_path}")


with open(json_file_path, 'r', encoding='utf-8') as file:
    data = json.load(file)

table_state = json.dumps(data['table_state'], indent=2)
balls_analysis = json.dumps(data['balls_analysis'], indent=2)
key_rule = data['system_context']['rules']
# print(key_rule)

prompt = f"美式9球游戏中当前台球台状态如下:{table_state}。球的分布信息如下：{balls_analysis}。请严格遵循规则: '{key_rule}'。给我一些击球建议。请在分析完成后给出总结。"

try:
    # 为了向后兼容性，可以使用 `https://api.deepseek.com/v1` 作为 `base_url`
    client = OpenAI(api_key="sk-0f350bf1d05d46dd82c0b99f9524f21e", base_url="https://api.deepseek.com/v1")

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
    print(f"正在读取分析结果: {absolute_analysis_result_path}")
    with open("analysis_result.txt", "w", encoding="utf-8") as f:
        f.write(content)
    # print(content)
    
except Exception as e:
    print(f"API调用失败: {str(e)}")
    with open("analysis_result.txt", "w", encoding="utf-8") as f:
        f.write(f"分析失败: {str(e)}")