#%%
## Import necessary libraries
# === 標準函式庫 ===
import re
import csv
import json
from collections import defaultdict

# === PyTorch / Transformers ===
import torch
from transformers import BertForSequenceClassification, BertTokenizer

# === 資料處理 / 機器學習 ===
import pandas as pd
from sklearn.cluster import DBSCAN

# === NLP / Embeddings ===
from sentence_transformers import SentenceTransformer

# === API / 其他工具 ===
import openai
import prompt

# OpenAI API key
with open("setting/key.txt", "r", encoding="utf-8") as f:
    openai.api_key = f.read().strip()

with open("MNS.txt", "r", encoding="utf-8") as f:
    data = f.read()

mqtt_dict = {}

# 找出所有符合格式的項目
matches = re.findall(r'\|\[(MQTT-[^\]]+)\]\|(.*?)\|', data, re.DOTALL)

for code, text in matches:
    mqtt_dict[code.strip()] = text.strip()

# 載入模型與 tokenizer
model = BertForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=2)
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
model.load_state_dict(torch.load('result/best_recall_model2', map_location='cpu'))

# 設定 device
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model.to(device)
model.eval()



#========== 方法 =========
# 判斷每一句是否為安全相關句子
def is_relevant(chunk, threshold=0.5):
    inputs = tokenizer(chunk, return_tensors="pt", padding=True, truncation=True, max_length=512)
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
    
    probs = torch.softmax(outputs.logits, dim=-1)
    return probs[:, 1].item() > threshold

filtered_mqtt_dict = {
    key: value for key, value in mqtt_dict.items()
    if is_relevant(value)
}

# 生成 constraint
def generate_security_constraint(chunk, reference, protocol="MQTT"):
    messages = [
        {"role": "system", "content": f"{reference}"},
        {"role": "user", "content": f"Part of the currently available {protocol} specifications:{chunk}"},
    ]

    completion = openai.ChatCompletion.create(
        model="gpt-4o",  
        messages=messages,
        response_format={"type": "json_object"}
    )

    print(completion.choices[0].message.content)

    return completion.choices[0].message.content 

# 對 constraint 進行分類成 priniciple
def principle_classification(sp_list, reference, ):
    messages = [
        {"role": "system", "content": f"{reference}"},
        {"role": "user", "content": f"{sp_list}"},
    ]

    completion = openai.ChatCompletion.create(
        model="gpt-4o",  
        messages=messages,
        response_format={"type": "json_object"}
    )

    return completion.choices[0].message.content  



# ===========DBSCAN 分群==========
# Step 1: 準備要編碼的句子
texts = list(filtered_mqtt_dict.values())
keys = list(filtered_mqtt_dict.keys())

# Step 2: 編碼
model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
chunk_embeddings = model.encode(texts)

# Step 3: 分群
dbscan = DBSCAN(eps=0.3, min_samples=1, metric='cosine')
labels = dbscan.fit_predict(chunk_embeddings)

# Step 4: 分群後將每個 cluster 對應的 key 和 text 存入
clusters = defaultdict(list)
for i, label in enumerate(labels):
    clusters[label].append((keys[i], texts[i]))

# Step 5: 將每個 cluster 的文字 concat 成一個 string
concatenated_clusters = {}
for label, items in clusters.items():
    texts_in_cluster = [text for _, text in items]
    concatenated_text = "\n".join(texts_in_cluster)
    concatenated_clusters[label] = concatenated_text



# ===========LLM 產生 securtiy principle 和 security constraint==========
referenceA = prompt.referenceA

with open("process/SP.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Cluster Label", "SP"])  

    for label, chunk in concatenated_clusters.items():
        result = generate_security_constraint(chunk, referenceA)

        if result:
            try:
                result_dict = json.loads(result)

                if isinstance(result_dict, dict) and "Security constraint" in result_dict:
                    sp_value = result_dict["Security constraint"]
                    writer.writerow([label, sp_value])
                else:
                    writer.writerow([label, str(result)])
            except json.JSONDecodeError:
                writer.writerow([label, str(result)])

print("\n所有结果已寫入 SP.csv")

# 移除 Security constraint 為 "No" 的項目
with open("process/SP.csv", "r", encoding="utf-8") as infile, \
     open("process/SP_remove_no.csv", "w", encoding="utf-8", newline="") as outfile:

    reader = csv.reader(infile)
    writer = csv.writer(outfile)

    header = next(reader)  
    writer.writerow(header)  

    new_label = 0  # 從0開始

    for row in reader:
        cluster_label, sp = row
        if sp.strip() != "No":
            writer.writerow([str(new_label), sp])
            new_label += 1

print("已移除 Security constraint 为 'No' 的项目，结果寫入 SP_remove_no.csv")

# 進行 security principle 分類
with open("process/SP_remove_no.csv", "r", encoding="utf-8") as f:
    sp_list = f.read()

referenceB = prompt.referenceB
new_principle_constraint = principle_classification(sp_list, referenceB)
print(new_principle_constraint)

# === 將 LLM 產生的 JSON 結果寫回 prompt.py ===
import ast

try:
    # 嘗試將 LLM 的回傳內容轉成 Python dict
    principles_dict = json.loads(new_principle_constraint)

    # 讀取 prompt.py 原內容
    with open("prompt.py", "r", encoding="utf-8") as f:
        prompt_content = f.read()

    # 轉換 dict → 美化後 JSON 字串
    formatted_json = json.dumps(principles_dict, indent=4, ensure_ascii=False)

    # 使用正則取代原本的 SP_principles 變數
    new_prompt_content = re.sub(
        r'SP_principles\s*=\s*\{.*?\}', 
        f'SP_principles = {formatted_json}', 
        prompt_content,
        flags=re.DOTALL
    )

    # 覆寫回 prompt.py
    with open("prompt.py", "w", encoding="utf-8") as f:
        f.write(new_prompt_content)

    print("✅ 已更新 prompt.py 中的 SP_principles 變數。")

except json.JSONDecodeError:
    print("⚠️ new_principle_constraint 不是有效的 JSON，未更新 prompt.py")
