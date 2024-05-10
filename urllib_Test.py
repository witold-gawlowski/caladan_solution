import http.client

# Sending a GET request using http.client
conn = http.client.HTTPSConnection('api.example.com')
conn.request('GET', '/data')
response = conn.getresponse()
data = response.read()
print(data.decode())  # Print 