# ./parse.py
- generate operations' metadata
    - Input is from /spec_segment/section_{xx}.txt
    - Original spec is in /spec/1.docx

- generate constrains
    - Use SYSTEM_PROMPT_2 and /spec_segment/section_6_4_6.txt

# ./input_format
- AllOpsMetaData.json: operations' metadata, used to construct uri for final extremal testing.
- {op}.json: constraints of each op, used to generate testing cases, i.e., test_input_format.


# TODO
- Please generate test cases for each ops
    - With 5 for each to see if test_free5gs.py/test_oai.py/test_open5gs.py can work.
- Generate more cases for ONLY Register, then extracting nfInstanceId from successful cases to fill the other operations' fields.
- Regenerate more cases for Deregister/Update/Subscribe.. to test.