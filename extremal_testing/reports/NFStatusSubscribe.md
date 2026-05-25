# NFStatusSubscribe Bug Report

- Source results: `/Users/adimehta/Desktop/School/ExtremalTesting/CS219/extremal_testing/json/test_results/NFStatusSubscribe.json`
- Source tests: `/Users/adimehta/Desktop/School/ExtremalTesting/CS219/extremal_testing/json/testcases/NFStatusSubscribe.json`
- Anomaly tests reviewed: 74
- Reports selected: 3

## 1. Discrepancy in Required Request Body Handling

The 'free5gc' implementation accepts requests with missing required fields in the request body, while 'oai' and 'open5gs' correctly return errors.

- Possibly affected implementations: free5gc
- Evidence strength: 9/10
- Rationale: 'free5gc' returns a 201 status code even when required fields are missing.
- Why investigate: Ensuring 'free5gc' correctly validates required fields could prevent unexpected behavior.

### Relevant Schema Evidence

| Schema ID | Location / Field | Required | Schema Summary |
| --- | --- | --- | --- |
| request_body | request_body.<root> | request_body=true; root_required=['nfStatusNotificationUri'] | application/json: target={"description": "Information of a subscription to notifications to NRF events, included in subscription requests and responses", "properties": {"completeProfileSubscription": {"type": "boolean"}, "extPreferredLocality": {"additionalProperties": {"items": {"$ref": "#/definition... |
| request_body.nfStatusNotificationUri | request_body.nfStatusNotificationUri | request_body=true; root_required=['nfStatusNotificationUri'] | application/json: target={"type": "string"} |

| Test | Constraint | Request | free5gc | oai | open5gs |
| --- | --- | --- | --- | --- | --- |
| tc_3_neg: Missing Request Body | request_body MUST be provided. | POST /subscriptions | status=201; body={"nfStatusNotificationUri":"","subscriptionId":"f355f50dfbfa5e40056bcd98de2980c5"} | status=400 | status=400; body={"title":"cannot parse HTTP message","status":400} |
| tc_5_neg: Missing nfStatusNotificationUri | request_body.nfStatusNotificationUri MUST be present. | POST /subscriptions | status=201; body={"nfStatusNotificationUri":"","subscriptionId":"b87ae65a625beed9d2c1fb7f96eccc60"} | status=400 | status=400; body={"title":"cannot parse HTTP message","status":400} |

## 2. Inconsistent Handling of Optional Header Fields

Different implementations show varying behavior when handling optional header fields 'Content-Encoding' and 'Accept-Encoding'. While 'free5gc' and 'oai' accept requests with or without these headers, 'open5gs' returns a 400 error.

- Possibly affected implementations: open5gs
- Evidence strength: 8/10
- Rationale: open5gs consistently returns a 400 error when optional headers are involved.
- Why investigate: Understanding why 'open5gs' fails on optional headers could improve interoperability.

### Relevant Schema Evidence

| Schema ID | Location / Field | Required | Schema Summary |
| --- | --- | --- | --- |
| header.Content-Encoding | header.Content-Encoding | false | {"type": "string"} |
| header.Accept-Encoding | header.Accept-Encoding | false | {"type": "string"} |

| Test | Constraint | Request | free5gc | oai | open5gs |
| --- | --- | --- | --- | --- | --- |
| tc_1_pos: Valid Content-Encoding Header | header.Content-Encoding MUST be a string. | POST /subscriptions | status=201; body={"nfStatusNotificationUri":"http://example.com/notify","subscriptionId":"223766518285292a2c94f4a34e754946"} | status=201; body={"nfStatusNotificationUri":"http://example.com/notify","notifCondition":{"monitoredAttributes":["nfStatus","fqdn"],"unmonitoredAttributes":["nfStatusChange"]},"reqNfInstanceId":"550e8400-e29b-41d4-a716-446655440000","reqNfType":"NRF","re... | status=400; body={"type":"/nnrf-nfm/v1","title":"No SubscrCond found in NF Subscription message","status":400,"instance":"/subscriptions"} |
| tc_1_neg: Invalid Content-Encoding Header | header.Content-Encoding MUST be a string. | POST /subscriptions | status=201; body={"nfStatusNotificationUri":"http://example.com/notify","subscriptionId":"effa6794f1f09fafd2dfdc0dfec21b4a"} | status=201; body={"nfStatusNotificationUri":"http://example.com/notify","notifCondition":{"monitoredAttributes":["nfStatus","fqdn"],"unmonitoredAttributes":["nfStatusChange"]},"reqNfInstanceId":"550e8400-e29b-41d4-a716-446655440000","reqNfType":"NRF","re... | status=400; body={"type":"/nnrf-nfm/v1","title":"No SubscrCond found in NF Subscription message","status":400,"instance":"/subscriptions"} |
| tc_2_pos: Valid Accept-Encoding Header | header.Accept-Encoding MUST be a string. | POST /subscriptions | status=201; body={"nfStatusNotificationUri":"http://example.com/notify","subscriptionId":"82690550bc3fe08d6a5aab9c6cdd5227"} | status=201; body={"nfStatusNotificationUri":"http://example.com/notify","notifCondition":{"monitoredAttributes":["nfStatus","fqdn"],"unmonitoredAttributes":["nfStatusChange"]},"reqNfInstanceId":"550e8400-e29b-41d4-a716-446655440000","reqNfType":"NRF","re... | status=400; body={"type":"/nnrf-nfm/v1","title":"No SubscrCond found in NF Subscription message","status":400,"instance":"/subscriptions"} |
| tc_2_neg: Invalid Accept-Encoding Header | header.Accept-Encoding MUST be a string. | POST /subscriptions | status=201; body={"nfStatusNotificationUri":"http://example.com/notify","subscriptionId":"5113b1630cda3993f529a9b2cf9aca77"} | status=201; body={"nfStatusNotificationUri":"http://example.com/notify","notifCondition":{"monitoredAttributes":["nfStatus","fqdn"],"unmonitoredAttributes":["nfStatusChange"]},"reqNfInstanceId":"550e8400-e29b-41d4-a716-446655440000","reqNfType":"NRF","re... | status=400; body={"type":"/nnrf-nfm/v1","title":"No SubscrCond found in NF Subscription message","status":400,"instance":"/subscriptions"} |

## 3. Handling of Invalid UUIDs in reqNfInstanceId

The 'free5gc' and 'oai' implementations accept invalid UUIDs for 'reqNfInstanceId', while 'open5gs' returns a 400 error.

- Possibly affected implementations: free5gc, oai
- Evidence strength: 7/10
- Rationale: Both 'free5gc' and 'oai' accept invalid UUIDs without error.
- Why investigate: Correct UUID validation is crucial for maintaining data integrity.

### Relevant Schema Evidence

| Schema ID | Location / Field | Required | Schema Summary |
| --- | --- | --- | --- |
| request_body.reqNfInstanceId | request_body.reqNfInstanceId | request_body=true; root_required=['nfStatusNotificationUri'] | application/json: target={"$ref": "#/definitions/TS29571_CommonData.NfInstanceId"} |

| Test | Constraint | Request | free5gc | oai | open5gs |
| --- | --- | --- | --- | --- | --- |
| tc_7_neg: Invalid UUID reqNfInstanceId | request_body.reqNfInstanceId MUST be a UUID version 4. | POST /subscriptions | status=201; body={"nfStatusNotificationUri":"http://example.com/notify","reqNfInstanceId":"invalid-uuid","subscriptionId":"123351f1e2acd52c85baa43dc0e0aa48"} | status=201; body={"nfStatusNotificationUri":"http://example.com/notify","notifCondition":{"monitoredAttributes":["nfStatus","fqdn"],"unmonitoredAttributes":["nfStatusChange"]},"reqNfInstanceId":"invalid-uuid","reqNfType":"NRF","reqNotifEvents":["NF_STATU... | status=400; body={"type":"/nnrf-nfm/v1","title":"No SubscrCond found in NF Subscription message","status":400,"instance":"/subscriptions"} |
