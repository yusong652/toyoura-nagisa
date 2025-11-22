Please only extract entities containing customer support information, order details, and user information. 
Here are some few shot examples:

Input: Hi.
Output: {"facts" : []}

Input: The weather is nice today.
Output: {"facts" : []}

Input: My order #12345 hasn't arrived yet.
Output: {"facts" : ["Order #12345 not received"]}

Input: I'm John Doe, and I'd like to return the shoes I bought last week.
Output: {"facts" : ["Customer name: John Doe", "Wants to return shoes", "Purchase made last week"]}

Input: I ordered a red shirt, size medium, but received a blue one instead.
Output: {"facts" : ["Ordered red shirt, size medium", "Received blue shirt instead"]}

Return the facts and customer information in a json format as shown above.