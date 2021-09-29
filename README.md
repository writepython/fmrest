# python2-fmrest

python2-fmrest is a wrapper around the FileMaker Data API.

No need to worry about manually requesting access tokens, setting the right http headers, parsing responses, ...

Quick example:

```python
>>> fms = fmrest.Server('https://your-server.com',
                        user='admin',
                        password='admin',
                        database='Contacts',
                        layout='Contacts')
>>> fms.login()
>>> record = fms.get_record(1)
>>> record.name
John Doe
```

## Supported Features

All API paths can be served:

- auth
- record
- find
- global
- script

