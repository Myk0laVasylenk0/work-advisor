import requests
import json

url = "https://jobs-api14.p.rapidapi.com/list"

headers = {
    "X-RapidAPI-Key": "f8aeec8e76msh2d835d623932470p1ce799jsn6efb4b8c4883",
    "X-RapidAPI-Host": "jobs-api14.p.rapidapi.com"
}

querystring = {"query": "Machine Learning", "location": "Kyiv, Ukraine", "distance": "1.0", "language": "en_GB",
               "remoteOnly": "false", "datePosted": "month", "employmentTypes": "fulltime;parttime;intern;contractor",
               "index": "0"}

response = requests.get(url, headers=headers, params=querystring)
response_dict = response.json()

# Print the response as a formatted JSON string for better readability
print()

print(response_dict)
