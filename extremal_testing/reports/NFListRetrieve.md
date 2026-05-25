# NFListRetrieve Bug Report

- Source results: `/Users/adimehta/Desktop/School/ExtremalTesting/CS219/extremal_testing/json/test_results/NFListRetrieve.json`
- Source tests: `/Users/adimehta/Desktop/School/ExtremalTesting/CS219/extremal_testing/json/testcases/NFListRetrieve.json`
- Anomaly tests reviewed: 16
- Reports selected: 3

## 1. Inconsistent Handling of 'limit', 'page-number', and 'page-size' Parameters

free5gc and oai return 400 errors for invalid 'limit', 'page-number', and 'page-size' values, while open5gs returns 200, suggesting inconsistent validation.

- Possibly affected implementations: open5gs
- Evidence strength: 9/10
- Rationale: open5gs does not enforce integer constraints on these parameters.
- Why investigate: Consistent parameter validation is essential for predictable API behavior.

### Relevant Schema Evidence

| Schema ID | Location / Field | Required | Schema Summary |
| --- | --- | --- | --- |
| query.limit | query.limit | false | {"minimum": 1, "type": "integer"} |
| query.page-number | query.page-number | false | {"minimum": 1, "type": "integer"} |
| query.page-size | query.page-size | false | {"minimum": 1, "type": "integer"} |

| Test | Constraint | Request | free5gc | oai | open5gs |
| --- | --- | --- | --- | --- | --- |
| tc_3_neg: Invalid limit as non-integer | query.limit MUST be an integer. | GET /nf-instances?limit=ten | status=400; body={"title":"nfType or limitParam empty","status":400,"detail":"nfType: , limitParam: ten"} | status=400 | status=200; body={"_links":{"item":[{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances/f57ade20-4e40-41f1-b347-39bae1d92074"}],"self":{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances"},"totalItemCount":1}} |
| tc_4_neg: Invalid limit less than 1 | query.limit MUST be greater than or equal to 1. | GET /nf-instances?limit=0 | status=400; body={"title":"nfType or limitParam empty","status":400,"detail":"nfType: , limitParam: 0"} | status=400; body={"cause":"MANDATORY_IE_INCORRECT"} | status=200; body={"_links":{"item":[{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances/f57ade20-4e40-41f1-b347-39bae1d92074"}],"self":{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances"},"totalItemCount":1}} |
| tc_5_neg: Invalid page-number as non-integer | query.page-number MUST be an integer. | GET /nf-instances?page-number=two | status=400; body={"title":"nfType or limitParam empty","status":400,"detail":"nfType: , limitParam: "} | status=400; body={"cause":"MANDATORY_IE_INCORRECT"} | status=200; body={"_links":{"item":[{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances/f57ade20-4e40-41f1-b347-39bae1d92074"}],"self":{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances"},"totalItemCount":1}} |
| tc_6_neg: Invalid page-number less than 1 | query.page-number MUST be greater than or equal to 1. | GET /nf-instances?page-number=0 | status=400; body={"title":"nfType or limitParam empty","status":400,"detail":"nfType: , limitParam: "} | status=400; body={"cause":"MANDATORY_IE_INCORRECT"} | status=200; body={"_links":{"item":[{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances/f57ade20-4e40-41f1-b347-39bae1d92074"}],"self":{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances"},"totalItemCount":1}} |
| tc_7_neg: Invalid page-size as non-integer | query.page-size MUST be an integer. | GET /nf-instances?page-size=five | status=400; body={"title":"nfType or limitParam empty","status":400,"detail":"nfType: , limitParam: "} | status=400; body={"cause":"MANDATORY_IE_INCORRECT"} | status=200; body={"_links":{"item":[{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances/f57ade20-4e40-41f1-b347-39bae1d92074"}],"self":{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances"},"totalItemCount":1}} |
| tc_8_neg: Invalid page-size less than 1 | query.page-size MUST be greater than or equal to 1. | GET /nf-instances?page-size=0 | status=400; body={"title":"nfType or limitParam empty","status":400,"detail":"nfType: , limitParam: "} | status=400; body={"cause":"MANDATORY_IE_INCORRECT"} | status=200; body={"_links":{"item":[{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances/f57ade20-4e40-41f1-b347-39bae1d92074"}],"self":{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances"},"totalItemCount":1}} |

## 2. Inconsistent Handling of Invalid 'nf-type' Parameter

When 'nf-type' is invalid, free5gc and oai return 400 errors, but open5gs returns 200, indicating a possible issue with input validation.

- Possibly affected implementations: open5gs
- Evidence strength: 9/10
- Rationale: open5gs accepts invalid 'nf-type' values without error.
- Why investigate: Ensuring consistent validation across implementations is crucial for reliability.

### Relevant Schema Evidence

| Schema ID | Location / Field | Required | Schema Summary |
| --- | --- | --- | --- |
| query.nf-type | query.nf-type | false | {"anyOf": [{"enum": ["NRF", "UDM", "AMF", "SMF", "AUSF", "NEF", "PCF", "SMSF", "NSSF", "UDR", "LMF", "GMLC", "5G_EIR", "SEPP", "UPF", "N3IWF", "AF", "UDSF", "BSF", "CHF", "NWDAF", "PCSCF", "CBCF", "HSS", "UCMF", "SOR_AF", "SPAF", "MME", "SCSAS", "SCEF", "SCP", "NSSAAF", "ICSCF", "SCSCF", "DRA", "IMS_AS", "AANF", "5G_DDNMF", "NSACF", "MFAF", "EASDF", "DCCF... |

| Test | Constraint | Request | free5gc | oai | open5gs |
| --- | --- | --- | --- | --- | --- |
| tc_1_neg: Invalid nf-type as non-string | query.nf-type MUST be a string. | GET /nf-instances?nf-type=123 | status=400; body={"title":"nfType or limitParam empty","status":400,"detail":"nfType: 123, limitParam: "} | status=400; body={"cause":"MANDATORY_IE_INCORRECT"} | status=200; body={"_links":{"item":[{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances/f57ade20-4e40-41f1-b347-39bae1d92074"}],"self":{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances"},"totalItemCount":1}} |
| tc_2_neg: Invalid nf-type as non-enumerated value | query.nf-type MUST be one of the enumerated NF types if specified. | GET /nf-instances?nf-type=INVALID_TYPE | status=400; body={"title":"nfType or limitParam empty","status":400,"detail":"nfType: INVALID_TYPE, limitParam: "} | status=400; body={"cause":"MANDATORY_IE_INCORRECT"} | status=200; body={"_links":{"item":[{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances/f57ade20-4e40-41f1-b347-39bae1d92074"}],"self":{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances"},"totalItemCount":1}} |

## 3. Inconsistent Handling of Valid 'nf-type' Parameter

Different implementations show inconsistent behavior when 'nf-type' is a valid string. free5gc returns a 400 error, while oai and open5gs return 200.

- Possibly affected implementations: free5gc
- Evidence strength: 8/10
- Rationale: free5gc returns an error for a valid 'nf-type' string.
- Why investigate: Understanding why free5gc fails on valid input could improve interoperability.

### Relevant Schema Evidence

| Schema ID | Location / Field | Required | Schema Summary |
| --- | --- | --- | --- |
| query.nf-type | query.nf-type | false | {"anyOf": [{"enum": ["NRF", "UDM", "AMF", "SMF", "AUSF", "NEF", "PCF", "SMSF", "NSSF", "UDR", "LMF", "GMLC", "5G_EIR", "SEPP", "UPF", "N3IWF", "AF", "UDSF", "BSF", "CHF", "NWDAF", "PCSCF", "CBCF", "HSS", "UCMF", "SOR_AF", "SPAF", "MME", "SCSAS", "SCEF", "SCP", "NSSAAF", "ICSCF", "SCSCF", "DRA", "IMS_AS", "AANF", "5G_DDNMF", "NSACF", "MFAF", "EASDF", "DCCF... |

| Test | Constraint | Request | free5gc | oai | open5gs |
| --- | --- | --- | --- | --- | --- |
| tc_1_pos: Valid nf-type as string | query.nf-type MUST be a string. | GET /nf-instances?nf-type=NRF | status=400; body={"title":"nfType or limitParam empty","status":400,"detail":"nfType: NRF, limitParam: "} | status=200; body={"_links":{"item":[],"self":""}} | status=200; body={"_links":{"item":[{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances/f57ade20-4e40-41f1-b347-39bae1d92074"}],"self":{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances"},"totalItemCount":1}} |
| tc_2_pos: Valid nf-type as enumerated value | query.nf-type MUST be one of the enumerated NF types if specified. | GET /nf-instances?nf-type=NRF | status=400; body={"title":"nfType or limitParam empty","status":400,"detail":"nfType: NRF, limitParam: "} | status=200; body={"_links":{"item":[],"self":""}} | status=200; body={"_links":{"item":[{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances/f57ade20-4e40-41f1-b347-39bae1d92074"}],"self":{"href":"http://0.0.0.0:7777/nnrf-nfm/v1/nf-instances"},"totalItemCount":1}} |
