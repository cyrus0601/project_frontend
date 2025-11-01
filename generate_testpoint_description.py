#%%
## Import necessary libraries
# === 標準函式庫 ===
import re
import csv
import json
import pathlib
import time

# === 資料處理 / 機器學習 ===
import pandas as pd

# === API / 其他工具 ===
import openai
import pymupdf4llm
import prompt

# OpenAI API key
with open("setting/key.txt", "r", encoding="utf-8") as f:
    openai.api_key = f.read().strip()



#========== 規格書切割 =========
# Step 1. PDF 轉 Markdown
markdown_content = pymupdf4llm.to_markdown("mqtt-v5.0.pdf")
pathlib.Path("mqtt-v5.0.md").write_bytes(markdown_content.encode("utf-8"))

# Step 2. 預處理句子
def remove_leading_numbers(sentence: str) -> str:
    """移除行首的數字和空白"""
    return re.sub(r'^\s*\d+', '', sentence)

with open('mqtt-v5.0.md', 'r', encoding='utf-8') as f:
    raw_sentences = f.read().split('\n')

processed_sentences = [
    remove_leading_numbers(s)
    for s in raw_sentences
    if s.strip() and s != "mqtt v5 0 os 07 March 2019"
]

# 先切分 cluster，遇到 "-----" 當分隔符
sentence_clusters = []
current_group = []

for s in processed_sentences:
    if s.strip() == "-----":
        if current_group:
            sentence_clusters.append(current_group)
            current_group = []
    else:
        current_group.append(s)

# 丟掉前 10 個 cluster，然後攤平成一條句子清單
sentence_clusters = sentence_clusters[10:]
flattened_sentences = [s for cluster in sentence_clusters for s in cluster]

# Step 3. 依標題 (**...**) 分群
pattern_title = r"\*\*(.*?)\*\*"
title_sentences = [s for s in flattened_sentences if re.search(pattern_title, s)]

sentence_clusters = []
current_group = []
current_section_id = None

def extract_section_id(title: str) -> str:
    """從標題擷取章節號（如 1.0、2.3.4），若無則回傳 'unknown'"""
    match = re.search(r"\b(\d+(?:\.\d+)*)(?!\w)", title)
    return match.group(1) if match else "unknown"

for s in flattened_sentences:
    if s in title_sentences:  # 新標題
        if current_group:
            sentence_clusters.append({
                "section": current_section_id,
                "content": current_group
            })
        current_section_id = extract_section_id(s)
        current_group = [s]
    else:
        current_group.append(s)

# 最後一組
if current_group:
    sentence_clusters.append({
        "section": current_section_id,
        "content": current_group
    })

# Step 4. 合併 cluster（依章節格式）
def is_two_level_section(section: str) -> bool:
    """判斷是否為兩層章節 (如 1.1, 2.3)"""
    return bool(re.fullmatch(r"\d+\.\d+", section))

merged_sentence_clusters = []
current_merged = None

for cluster in sentence_clusters:
    section_id = cluster["section"]

    if current_merged is None:
        current_merged = {
            "section": section_id,
            "content": cluster["content"].copy()
        }
        continue

    if is_two_level_section(section_id) and section_id != current_merged["section"]:
        # 開新 cluster
        merged_sentence_clusters.append(current_merged)
        current_merged = {
            "section": section_id,
            "content": cluster["content"].copy()
        }
    else:
        # 合併
        current_merged["content"].extend(cluster["content"])

if current_merged:
    merged_sentence_clusters.append(current_merged)



#========== 取得測試點描述 =========
referenceC = prompt.referenceC

def process_chunk_with_gpt_violation(cluster, reference ):
    messages = [
        {"role": "system", "content": f"{reference}"},
        {"role": "user", "content": f"{cluster}"},
    ]

    completion = openai.ChatCompletion.create(
        model="gpt-4o",  # Use the appropriate model name
        messages=messages,
        response_format={"type": "json_object"}
    )
    return completion.choices[0].message.content  # 返回完整的內容

with open("process/violation_output.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Cluster Index", "Principles", "Properties", "Description"])

    for i, cluster in enumerate(merged_sentence_clusters, 1):
        if 6 < i < 48:
            print(f"Processing cluster {i}...")
            response = process_chunk_with_gpt_violation(cluster["content"], referenceC)

            try:
                result = json.loads(response)

                if "matched_principles" in result:
                    principles = result["matched_principles"]
                    if any(p["principle"] != "No" for p in principles):
                        clean_cluster = "\n".join(cluster["content"]).strip()
                        for item in principles:
                            if item["principle"] != "No":
                                writer.writerow([
                                    i,
                                    item.get("principle", ""),
                                    item.get("constraint", ""),
                                    item.get("reason", ""),
                                    cluster.get("section", "")
                                ])
            except json.JSONDecodeError:
                print(f"[Error] JSON decode failed at cluster {i}")

# Define the prompt for GPT
referenceD = prompt.referenceD

# Function to call GPT and process the response
def final_ask(referenceD, cluster, properties, reason, principle):
    conversation = [
        {"role": "system", "content": referenceD},
        {"role": "user", "content": f"""
Specification: {cluster}
------
HighLevelPrinciple: {principle}
------
SecurityProperties: {properties}
-----
Reason: {reason}
"""}
    ]
    
    stream = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=conversation,
        stream=True,
        response_format={"type": "json_object"}
    )

    full_response = ""
    for response in stream:
        content = response.get("choices", [{}])[0].get("delta", {}).get("content")
        if content:
            full_response += content

    return full_response


# %%
#========== 移除增強描述沒通過的描述 =========
filename = "process/violation_output.csv"
output_filename = "process/processed_violation_output.csv"

with open(filename, newline="", encoding="utf-8") as csvfile, open(output_filename, "w", encoding="utf-8", newline="") as outputfile:
    reader = csv.DictReader(csvfile)
    writer = csv.writer(outputfile)
    writer.writerow(["Cluster Index", "Principles", "Properties", "EnhancedDescription"])  # Write headers

    for row in reader:
        cluster_index = row["Cluster Index"]
        principle = row["Principles"]
        properties = row["Properties"]
        reason = row["Description"]

        try:
            idx = int(cluster_index) - 1
            if 0 <= idx < len(merged_sentence_clusters):
                cluster = "\n".join(merged_sentence_clusters[idx]["content"])

                print(f"\nProcessing Cluster {cluster_index}...")

                result = final_ask(referenceD, cluster, properties, reason, principle)
                print(result)
                try:
                    result_json = json.loads(result)
                    enhanced = result_json.get("EnhancedDescription", "").strip()
                except json.JSONDecodeError:
                    enhanced = result.strip()  # fallback to raw result

                writer.writerow([cluster_index, principle, properties, enhanced])
            else:
                print(f"[Warning] Cluster index {cluster_index} out of range.")
        except Exception as e:
            print(f"[Error] Failed to process cluster {cluster_index}: {e}")

# Step 1: Read the processed CSV file and filter out rows with 'No' in the 'EnhancedDescription' column
input_filename = "process/processed_violation_output.csv"
output_filename = "process/filtered_violation_output.csv"

# Open the original processed file
with open(input_filename, newline="", encoding="utf-8") as inputfile, \
        open(output_filename, "w", encoding="utf-8", newline="") as outputfile:

    reader = csv.DictReader(inputfile)
    fieldnames = reader.fieldnames  # Get the header from the original file
    writer = csv.DictWriter(outputfile, fieldnames=fieldnames)

    writer.writeheader()  # Write the header to the output file

    # Step 2: Process each row, check if 'EnhancedDescription' is 'No' and filter it out
    for row in reader:
        if row['EnhancedDescription'] == "No":  # Skip rows with 'No' in EnhancedDescription
            continue
        else:
            writer.writerow(row)  


#========== 移除不被一致性通過的描述 =========
referenceE = prompt.referenceE

def TF(referenceE, enhanced_description, max_retries=5, delay=5):
    messages = [
        {"role": "system", "content": referenceE},
        {"role": "user", "content": f"Vulnerability description: {enhanced_description}"}
    ]

    for attempt in range(max_retries):
        try:
            stream = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=messages,
                stream=True,
            )

            full_response = ""
            for response in stream:
                content = response.get("choices", [{}])[0].get("delta", {}).get("content")
                if content:
                    full_response += content

            return full_response.strip()

        except openai.error.ServiceUnavailableError:
            print(f"[!] Server unavailable, retrying in {delay} sec... (attempt {attempt+1}/{max_retries})")
            time.sleep(delay)

    raise RuntimeError("Failed after max retries due to ServiceUnavailableError.")

# 投票分類邏輯
def classify_votes(row):
    votes = [row["First"], row["Second"], row["Third"]]
    no_count = sum(v.strip() == "F" for v in votes)

    if no_count == 3:
        return "3"
    elif no_count == 2:
        return "2"
    elif no_count == 1:
        return "1"
    else:
        return "-"

#  迴圈處理邏輯
MAX_ROUNDS = 10

for round_idx in range(1, MAX_ROUNDS + 1):
    print(f"\n=== Round {round_idx} ===")

    # 讀取當前輸入資料
    df = pd.read_csv("process/filtered_violation_output.csv", encoding="utf-8")

    results = []
    for i, row in df.iterrows():
        cluster = row["Cluster Index"]
        enhanced_description = row["EnhancedDescription"]

        print(f"[+] Processing Cluster {cluster} (Row {i+2})")

        run_results = []
        for r in range(3):
            print(f"  - Run {r+1}")
            result = TF(referenceE, enhanced_description)
            run_results.append(result)
            time.sleep(1)  # 降低 API 請求壓力

        results.append({
            "Cluster": cluster,
            "First": run_results[0],
            "Second": run_results[1],
            "Third": run_results[2]
        })

    # 存下 GPT 投票結果
    output_df = pd.DataFrame(results)
    vote_path = "process/constraint_violation_vote.csv"
    output_df.to_csv(vote_path, index=False, encoding="utf-8")

    # 讀取並加上投票分類
    df_votes = pd.read_csv(vote_path, encoding="utf-8")
    df_votes["Vote Classification"] = df_votes.apply(classify_votes, axis=1)
    classified_path = "process/TF_votes_result.csv"
    df_votes.to_csv(classified_path, index=False, encoding="utf-8")

    # 更新 filtered_violation_output.csv
    keep_mask = df_votes["Vote Classification"] == "-"
    filtered_df = df[keep_mask]

    removed_count = len(df) - len(filtered_df)
    print(f"Removed {removed_count} clusters in round {round_idx}")

    filtered_df.to_csv("process/filtered_violation_output.csv", index=False, encoding="utf-8")


    filtered_cluster_path = "process/filtered_violation_output_description_only.csv"
    filtered_df[["Cluster Index", "EnhancedDescription"]].to_csv(filtered_cluster_path, index=False, encoding="utf-8")

    # 如果沒有東西被移除就提前停止
    if removed_count == 0:
        print("No more clusters removed. Stopping early.")
        break

# %%
import prompt
print(prompt.referenceC)
# %%
