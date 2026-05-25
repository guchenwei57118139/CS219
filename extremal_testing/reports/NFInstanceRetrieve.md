# NFInstanceRetrieve Bug Report

- Source results: `/Users/adimehta/Desktop/School/ExtremalTesting/CS219/extremal_testing/json/test_results/NFInstanceRetrieve.json`
- Source tests: `/Users/adimehta/Desktop/School/ExtremalTesting/CS219/extremal_testing/json/testcases/NFInstanceRetrieve.json`
- Anomaly tests reviewed: 1
- Reports selected: 1

## 1. Inconsistent Handling of Invalid Requester-Features Pattern

Observed inconsistency in handling invalid 'requester-features' query parameter pattern. The parameter did not match the required pattern ^[A-Fa-f0-9]*$, yet different implementations responded differently.

- Possibly affected implementations: free5gc, oai, open5gs
- Evidence strength: 8/10
- Rationale: free5gc and oai returned 200 OK, while open5gs returned 400 Bad Request for the same invalid input.
- Why investigate: Understanding how implementations validate query parameters can improve interoperability and compliance with specifications.

### Relevant Schema Evidence

| Schema ID | Location / Field | Required | Schema Summary |
| --- | --- | --- | --- |
| query.requester-features | query.requester-features | false | {"description": "A string used to indicate the features supported by an API that is used as defined in clause 6.6 in 3GPP TS 29.500. The string shall contain a bitmask indicating supported features in hexadecimal representation Each c...", "pattern": "^[A-Fa-f0-9]*$", "type": "string"} |

| Test | Constraint | Request | free5gc | oai | open5gs |
| --- | --- | --- | --- | --- | --- |
| tc_5_neg: Invalid Pattern Requester-Features | query.requester-features MUST match the pattern ^[A-Fa-f0-9]*$. | GET /nf-instances/{nfInstanceId}?requester-features=1A2B3G | status=200; body={"customInfo":{"oauth2":false},"fqdn":"nrf.example.3gppnetwork.org","nfInstanceId":"48464adc-4f3d-5a07-8d12-4225fe52a7ed","nfStatus":"REGISTERED","nfType":"NRF","plmnList":[{"mcc":"208","mnc":"93"}]} | status=200; body={"capacity":0,"fqdn":"nrf.example.3gppnetwork.org","heartBeatTimer":10,"ipv4Addresses":[],"json_data":null,"nfInstanceId":"48464adc-4f3d-5a07-8d12-4225fe52a7ed","nfInstanceName":"","nfServices":[],"nfStatus":"REGISTERED","nfType":"NF TYP... | status=400; body={"title":"cannot parse HTTP message","status":400} |
