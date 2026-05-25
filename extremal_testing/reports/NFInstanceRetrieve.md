# NFInstanceRetrieve Bug Report

- Source results: `/Users/adimehta/Desktop/School/ExtremalTesting/CS219/extremal_testing/json/test_results/NFInstanceRetrieve.json`
- Source tests: `/Users/adimehta/Desktop/School/ExtremalTesting/CS219/extremal_testing/json/testcases/NFInstanceRetrieve.json`
- Anomaly tests reviewed: 1
- Reports selected: 1

## 1. Open5GS Enforces Stricter Validation on requester-features

Open5GS returns a 400 error when the requester-features query parameter does not match the expected pattern ^[A-Fa-f0-9]*$. This suggests Open5GS may be enforcing stricter validation than other implementations.

- Possibly affected implementations: open5gs
- Evidence strength: 8/10
- Rationale: Open5GS consistently returns a 400 error for invalid requester-features patterns, unlike other implementations.
- Implementation differences: Open5GS returns 400 with error "cannot parse HTTP message" while free5gc and oai return 200.
- Why investigate: This behavior indicates a possible discrepancy in pattern validation for optional fields, which could affect interoperability.

### Relevant Schema Evidence

| Schema ID | Location / Field | Required | Schema Summary |
| --- | --- | --- | --- |
| query.requester-features | query.requester-features | false | {"description": "A string used to indicate the features supported by an API that is used as defined in clause 6.6 in 3GPP TS 29.500. The string shall contain a bitmask indicating supported features in hexadecimal representation Each c...", "pattern": "^[A-Fa-f0-9]*$", "type": "string"} |

| Test | Constraint | Request | free5gc | oai | open5gs |
| --- | --- | --- | --- | --- | --- |
| tc_5_neg: Invalid Pattern Requester-Features | query.requester-features MUST match the pattern ^[A-Fa-f0-9]*$. | GET /nf-instances/{nfInstanceId}?requester-features=1A2B3G | status=200; body={"customInfo":{"oauth2":false},"fqdn":"nrf.example.3gppnetwork.org","nfInstanceId":"48464adc-4f3d-5a07-8d12-4225fe52a7ed","nfStatus":"REGISTERED","nfType":"NRF","plmnList":[{"mcc":"208","mnc":"93"}]} | status=200; body={"capacity":0,"fqdn":"nrf.example.3gppnetwork.org","heartBeatTimer":10,"ipv4Addresses":[],"json_data":null,"nfInstanceId":"48464adc-4f3d-5a07-8d12-4225fe52a7ed","nfInstanceName":"","nfServices":[],"nfStatus":"REGISTERED","nfType":"NF TYP... | status=400; body={"title":"cannot parse HTTP message","status":400} |
