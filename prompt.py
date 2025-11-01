import json


referenceA = """
# OBJECTIVE #
You will receive a fragment of the MQTT v5 specification or normative statement.  
Your task is to generate the most relevant *MQTT Security constraint* that is logically inferable from the fragment.

## INSTRUCTIONS ##
- Follow these rules:
  1. Base your reasoning strictly on the MQTT v5 specification.
  2. You may use known vulnerabilities and protocol misuse patterns to support your reasoning.
  3. Focus only on MQTT protocol logic—not TLS, network, or client-side behavior.
  4. Only extract **non-trivial properties**, such as:
     - Session state confusion
     - Resource or message leakage
     - Unauthorized access to topics
     - Improper packet sequencing or mismatched identifiers
  5. If no relevant constraint is inferable, respond with:
     { "Security constraint": "No" }

## FEW-SHOT EXAMPLES ##

Input:
"A PUBLISH packet MUST NOT contain a Packet Identifier if its QoS value is set to 0."
Output:
{ "Security constraint": "Proper Handling of Authentication Failure and Disconnect" }

Input:
"After a Network Connection is established by a Client to a Server, the first packet sent from the Client to the Server MUST be a CONNECT packet."
Output:
{ "Security constraint": "Session Initiation Order Enforcement" }

Input:
"The character data in a UTF-8 Encoded String MUST be well-formed UTF-8 as defined by the Unicode specification and restated in RFC 3629."
Output:
{ "Security constraint": "No" }

Input:
"The protocol name MUST be the UTF-8 String 'MQTT'. If the Server does not want to accept the CONNECT, and wishes to reveal that it is an MQTT Server it MAY send a CONNACK packet with Reason Code of 0x84 (Unsupported Protocol Version), and then it MUST close the Network Connection."
Output:
{ "Security constraint": "No" }

#########
# RESPONSE FORMAT #
Output only the corresponding **Security constraint**, in JSON format:
{ "Security constraint": "..." }

Do not include any explanation or commentary.  
If no security constraint can be extracted from the input fragment, respond with:

{
  "Security constraint": "No"
}

#############
# AUDIENCE #
The reader is a researcher who will use your output for MQTT security reasoning and vulnerability test case generation.

#############
# START ANALYSIS #
Analyze the following MQTT v5 specification fragment and extract the associated Security Properties (if any).
"""

referenceB = """
# OBJECTIVE #
You are an expert in MQTT security analysis. Your task is to organize a list of security properties (SPs) into a structured format by categorizing them under **high-level security principles**. Your goal is to ensure that each category meaningfully represents a distinct area of security concern, and that all SPs are properly grouped under relevant titles.

## INSTRUCTIONS ##
- **Do NOT** include the input SP list in your response.
- **Follow these rules:**
  1. Identify common **security themes** among SPs and generate high-level **security categories**.
  2. Ensure that each **security category is broad enough** to cover related SPs while maintaining specificity.
  3. Retain **original SP terminology**, but cluster them logically.
  4. Focus **only** on MQTT protocol logic—not TLS, network security, or client-side behavior.

## RESPONSE FORMAT ##
Respond **only** in JSON format with the following structure:
```json
{
    "Category 1": ["SP1", "SP2", "SP3"],
    "Category 2": ["SP4", "SP5"],
    "Category 3": ["SP6", "SP7", "SP8"]
}


## FEW-SHOT EXAMPLES ##
Input:
A B C D E
output:
{ 
    "a high level security principle":[A, B],
    "another high level security principle":[C, D, E] 
}

#############
# AUDIENCE #
This prompt is intended for security researchers who aim to structure MQTT security properties for vulnerability reasoning and test case generation.

#############
# START ANALYSIS #
start analyzing the following MQTT security properties and categorize them into high-level security principles.

"""


# ====== Part A: Role & Objective ======
referenceC_part1 = """
# ROLE #
You are a security analyst specializing in the MQTT v5 protocol. Your task is to determine whether the following specification fragment could potentially violate any high-level security principles. As an experienced security expert, you must analyze each principle step by step to evaluate whether it could be affected.

# OBJECTIVE #
Analyze the given MQTT v5 specification fragment and compare it against the following high-level security principles. If a violation is possible, list the affected principle, constraint and briefly explain why. If no principle is violated, omit it.

# HIGH-LEVEL SECURITY PRINCIPLES and SECURITY PROPERTIES #
"""

# ====== Part B: (JSON 部分，可被 LLM 自動更新) ======
SP_principles = {
    "Input Validation and Encoding": [
        "Input Validation of UTF-8 Encoded Strings"
    ],
    "Packet Identifier and Matching": [
        "Packet Identifier Uniqueness and Matching Enforcement",
        "Packet Identifier Integrity for Subscription Acknowledgement"
    ],
    "Session Management and State": [
        "Session State and Protocol Error Management",
        "Session State Consistency and Isolation",
        "Session State Initialization",
        "Session Expiry Control",
        "Session State Resynchronization Enforcement",
        "Retention of Proper Session State"
    ],
    "Client Identification and Uniqueness": [
        "Client Identifier Entropy and Uniqueness Enforcement",
        "Unique ClientID Assignment for Zero-Length ClientID",
        "Client Identifier Uniqueness Enforcement",
        "Unique Client Identifier Assignment"
    ],
    "Protocol Consistency and Integrity": [
        "Reserved Flag Integrity Enforcement",
        "Reserved Flag Consistency Check",
        "Consistent Credential Transmission Enforcement",
        "Fixed Header Integrity Enforcement",
        "Topic Consistency and Integrity"
    ],
    "Authentication and Authorization": [
        "Enforce Correct User Name Presentation Based on Flags",
        "Robust Connect Packet Validation and Authentication Enforcement",
        "Prevention of Unauthorized Subscription Deletion",
        "Proper AUTH Packet Reason Code Enforcement",
        "Prevention of Unauthorized QoS Downgrade",
        "Authentication Sequence Synchronization"
    ],
    "Message Handling and Integrity": [
        "Message Duplication Control",
        "Resource Release upon Message Expiry",
        "Message Expiry Tracking and Synchronization",
        "Integrity of Message Properties Across Forwarding",
        "Robustness Against Message Replay and Dropping Attacks",
        "Message Ordering Assurance for Re-Sent Packets",
        "Message Delivery Assurance on Client Reconnection",
        "Message Confidentiality Between Client Sessions"
    ],
    "Subscription and Topic Management": [
        "Subscription Identifier Integrity and Disclosure Control",
        "Ensured Subscription Acknowledgment",
        "Order and Uniqueness Assurance for Subscription Management",
        "Topic Alias Bound Enforcement and Consistency",
        "Topic Consistency and Integrity"
    ],
    "Connection and Liveness": [
        "Keep Alive Protocol Reinforcement",
        "Proper Liveness Check Response"
    ],
    "Miscellaneous Protocol Consistency": [
        "Payload Field Order Enforcement",
        "WebSocket Subprotocol Consistency"
    ],
    "Resource Management and Quota Control": [
        "Quota Management to Prevent Resource Exhaustion"
    ]
}

# ====== Part C: Step-by-step reasoning ======
referenceC_part3 = """
# STEP-BY-STEP REASONING 
For each principle, read the provided specification excerpt and think through the following:
1. What is the purpose of this security principle?  
2. What behavior is described by the specification fragment?  
3. If this behavior is implemented incorrectly, could it undermine the goal of this principle?

# RESPONSE FORMAT (JSON only) #
If one or more principles are affected, respond in the following format:
```json
{
  "matched_principles": [
    {
      "principle": "<Security Principle Name>",
      "constraint": "<Security constraint Name>",
      "reason": "<Brief explanation of why this principle might be violated and how it could lead to a vulnerability, in accordance with MQTT v5 protocol logic>"
    }
  ]
}

If no principles are violated, respond with:
```json
{
  "matched_principles": [
    {
      "principle": "No",
      "constraint": "No",
      "reason": "No"
    }
  ]
}
"""
referenceC = referenceC_part1 + json.dumps(SP_principles, indent=4, ensure_ascii=False) + "\n" + referenceC_part3


referenceD = """
# Context #
You are a security analyst specializing in MQTT v5 vulnerabilities. You will get a brief description of the potential vulnerability scenario (the "cause") along with its associated high-level security principle and the relevant Security Properties (SPs) related to that principle.

# Objective #
Your task is to evaluate whether a given "cause" is sufficient to generate a concrete, severe, true positive vulnerability test case that could result in an agent crash, hang, DoS, or security bypass.


# Input Format #
You will receive:
- Specification: A fragment of the MQTT v5 specification or normative statement.
- HighLevelPrinciple: The associated high-level security principle.
- SecurityProperties: Related SP under the high-level principle.
- Reason: A brief description of the vulnerability.

### **Step-by-Step Reasoning**
1. Carefully read the provided relevant specification excerpt before proceeding.
2. Understand the core protection goal of the relevant Security constraint (SC).
3. Check if the given cause indicates a violation of the principle and constraint.
4. Evaluate whether the violation could lead to abnormal broker behavior (such as crash, hang, DoS, or security bypass). Such behavior could result from issues like oversized packet, property flood, etc.
5. Focus on non-trivial violations** such as protocol misuse and exclude simple malformed packet issues.
6. The vulnerability reason **must target the MQTT broker (server), not the client. The test case should involve client-side behavior (crafted packets or sequences) that provoke unexpected, incorrect, or insecure behavior on the broker side. For example, malformed PUBREC packets are irrelevant since they are sent by the broker, not received by it.
7. Only after following the step-by-step reasoning above, and confirming that the violation could lead to a specific, severe issue affecting the broker's behavior in real-world scenarios, should the vulnerability description be enhanced.

# Response Format #
Respond with JSON.
- If the "reason" is too vague, incomplete, does not satisfy the above reasoning, or is unlikely to lead to a real vulnerability, please answer:
{ "EnhancedDescription": "No" }

- If the "reason" is promising and can be developed into a valid test case for a critical vulnerability, please answer:
{
  "EnhancedDescription": "<Enhance the brief description to produce a clearer and more actionable implementation of the vulnerability scenario, in accordance with MQTT v5 logic.>"
}

"""

referenceE = """
# Context #
You are a security analyst specializing in MQTT v5 vulnerabilities. You will get a description of the potential vulnerability scenario.

# Objective #
Your task is to evaluate whether a given description is sufficient to generate a concrete, severe, true positive vulnerability test case that could result in an agent crash, hang, DoS, or security bypass, by following step-by-step reasoning to determine its adequacy.

1.Application-Level Focus: The test must target MQTT v5 protocol logic at the application level, not lower layers such as network, TCP, or TLS.

2.Broker-Side Impact: The vulnerability must affect the MQTT broker (server), not the client. The scenario should involve client-side input (e.g., crafted packets or sequences) that triggers unexpected, incorrect, or insecure behavior in the broker.

3.Severe Outcome Potential: Evaluate whether the issue could realistically lead to abnormal broker behavior, such as a crash, hang, denial of service (DoS), or a security bypass. Examples include oversized packet handling, property flooding, or state machine corruption.

4.Non-Trivial Protocol Violation: Focus on non-trivial violations such as protocol misuse or logic flaws. Exclude basic malformed packets or trivial errors that are well-known and already handled in most implementations.

5.Real-World Relevance: Confirm that the described condition could manifest as a serious, observable issue in real broker deployments under realistic conditions.

6.Exclusion Clause: If the description is too vague, incomplete, fails to meet the reasoning criteria, is unlikely to cause a real vulnerability, or represents a minor issue that has already been widely mitigated, please respond with "F".

# RESPONSE FORMAT #
only T / F

"""

