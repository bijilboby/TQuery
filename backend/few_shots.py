few_shots = [
    {'Question' : "How many t-shirts do we have left for Nike in XS size and white color?",
     'SQLQuery' : "SELECT sum(stock_quantity) FROM t_shirts WHERE brand = 'Nike' AND color = 'White' AND size = 'XS'",
     'SQLResult': "[(Decimal('92'),)]",
     'Answer' : "We currently have 92 Nike XS white t-shirts in stock."},
    
    {'Question': "How much is the total price of the inventory for all S-size t-shirts?",
     'SQLQuery':"SELECT SUM(price*stock_quantity) FROM t_shirts WHERE size = 'S'",
     'SQLResult': "[(Decimal('24230'),)]",
     'Answer': "The total inventory value for all S-size t-shirts is ₹24,230."},
     
    {'Question': "If we have to sell all the Levi's T-shirts today with discounts applied. How much revenue our store will generate (post discounts)?" ,
     'SQLQuery' : """SELECT sum(a.total_amount * ((100-COALESCE(discounts.pct_discount,0))/100)) as total_revenue from
(select sum(price*stock_quantity) as total_amount, t_shirt_id from t_shirts where brand = 'Levi'
group by t_shirt_id) a left join discounts on a.t_shirt_id = discounts.t_shirt_id
 """,
     'SQLResult': "[(Decimal('31098.000000'),)]",
     'Answer': "If you sell all Levi's t-shirts today with current discounts applied, you would generate ₹31,098 in revenue."} ,
     
     {'Question' : "If we have to sell all the Levi's T-shirts today. How much revenue our store will generate without discount?" ,
      'SQLQuery': "SELECT SUM(price * stock_quantity) FROM t_shirts WHERE brand = 'Levi'",
      'SQLResult': "[(Decimal('36100'),)]",
      'Answer' : "Selling all Levi's t-shirts at full price (without discounts) would generate ₹36,100 in revenue."},
      
    {'Question': "How many white color Levi's shirt I have?",
     'SQLQuery' : "SELECT sum(stock_quantity) FROM t_shirts WHERE brand = 'Levi' AND color = 'White'",
     'SQLResult': "[(Decimal('325'),)]",
     'Answer' : "You have 325 white Levi's t-shirts in your inventory."
     },
     
    {'Question': "How many Nike t-shirts do we have in total?",
      'SQLQuery': "SELECT SUM(stock_quantity) FROM t_shirts WHERE brand = 'Nike'",
      'SQLResult': "[(Decimal('1063'),)]",
      'Answer': "You have a total of 1,063 Nike t-shirts in stock."
    },
    
    {"Question": "How many t-shirts of brand Ding Don do we have?",
      "SQLQuery": "SELECT COUNT(*) FROM t_shirts WHERE brand = 'Ding Don'",
      "SQLResult": "[(0,)]",
      "Answer": "I couldn't find any t-shirts from the brand 'Ding Don' in your inventory. We currently carry Nike, Adidas, Levi, and Van Huesen brands."
    },

    {"Question": "How many black t-shirts of brand Ding Don do we have?",
      "SQLQuery": "SELECT COUNT(*) FROM t_shirts WHERE brand = 'Ding Don' AND color = 'Black'",
      "SQLResult": "[(0,)]",
      "Answer": "I couldn't find any t-shirts from the brand 'Ding Don' in your inventory. We currently carry Nike, Adidas, Levi, and Van Huesen brands."
    },
    
    {
    "Question": "What colors are available for Adidas t-shirts?",
    "SQLQuery": "SELECT DISTINCT color FROM t_shirts WHERE brand = 'Adidas'",
    "SQLResult": "[('Red',), ('Blue',), ('Black',), ('White',)]",
    "Answer": "Adidas t-shirts are available in Red, Blue, Black, and White colors."
    },
    
    {
    "Question": "What colors are available for Levi t-shirts?",
    "SQLQuery": "SELECT DISTINCT color FROM t_shirts WHERE brand = 'Levi'",
    "SQLResult": "[('Red',), ('Blue',), ('Black',), ('White',)]",
    "Answer": "Levi t-shirts are available in Red, Blue, Black, and White colors."
    },
    
    {
    "Question": "Which t-shirt brands do we have in our store?",
    "SQLQuery": "SELECT DISTINCT brand FROM t_shirts",
    "SQLResult": "[('Nike',), ('Adidas',), ('Levi',), ('Van Huesen',)]",
    "Answer": "We carry four t-shirt brands: Nike, Adidas, Levi, and Van Huesen."
    },
    
    {
    "Question": "What sizes are available for Nike t-shirts?",
    "SQLQuery": "SELECT DISTINCT size FROM t_shirts WHERE brand = 'Nike' ORDER BY FIELD(size, 'XS', 'S', 'M', 'L', 'XL')",
    "SQLResult": "[('XS',), ('S',), ('M',), ('L',), ('XL',)]",
    "Answer": "Nike t-shirts are available in all sizes: XS, S, M, L, and XL."
    },
    
    {
    "Question": "How much would it cost to buy all the red t-shirts?",
    "SQLQuery": "SELECT SUM(price * stock_quantity) FROM t_shirts WHERE color = 'Red'",
    "SQLResult": "[(Decimal('35590'),)]",
    "Answer": "The total cost to purchase all red t-shirts in inventory would be ₹35,590."
    },
    
    {
    "Question": "Which brand has the most t-shirts in stock?",
    "SQLQuery": "SELECT brand, SUM(stock_quantity) as total_stock FROM t_shirts GROUP BY brand ORDER BY total_stock DESC LIMIT 1",
    "SQLResult": "[('Levi', Decimal('1111'))]",
    "Answer": "Levi has the most t-shirts in stock with 1,111 units."
    },
    
    {
    "Question": "Are there any discounts available on Van Huesen t-shirts?",
    "SQLQuery": "SELECT DISTINCT t.brand, d.pct_discount FROM t_shirts t LEFT JOIN discounts d ON t.t_shirt_id = d.t_shirt_id WHERE t.brand = 'Van Huesen' AND d.pct_discount IS NOT NULL",
    "SQLResult": "[('Van Huesen', Decimal('10.00'))]",
    "Answer": "Yes, there's a 10% discount available on some Van Huesen t-shirts."
    },
    
    {
    "Question": "What is the total discounted value of all t-shirts larger than size 'M'?",
    "SQLQuery": "SELECT SUM(t.price * t.stock_quantity * (100 - COALESCE(d.pct_discount, 0)) / 100) AS total_discounted_value FROM t_shirts t LEFT JOIN discounts d ON t.t_shirt_id = d.t_shirt_id WHERE t.size IN ('L', 'XL')",
    "SQLResult": "[(Decimal('156420.00'),)]",
    "Answer": "The total discounted value of all t-shirts in sizes L and XL is ₹156,420."
    },
    
    {
    "Question": "What is the total value of all discounted t-shirts?",
    "SQLQuery": "SELECT SUM(t.price * t.stock_quantity * (100 - d.pct_discount) / 100) AS discounted_total FROM t_shirts t INNER JOIN discounts d ON t.t_shirt_id = d.t_shirt_id",
    "SQLResult": "[(Decimal('89210.00'),)]",
    "Answer": "The total value of all discounted t-shirts after applying discounts is ₹89,210."
    },
    
    {
    "Question": "How much would we save if we applied a 15% discount to all Nike t-shirts?",
    "SQLQuery": "SELECT SUM(t.price * t.stock_quantity * 0.15) AS total_savings FROM t_shirts t WHERE t.brand = 'Nike'",
    "SQLResult": "[(Decimal('7845.00'),)]",
    "Answer": "If you applied a 15% discount to all Nike t-shirts, you would save customers a total of ₹7,845."
    },
    
    {
    "Question": "What is the total undiscounted value of all t-shirts?",
    "SQLQuery": "SELECT SUM(price * stock_quantity) AS total_value FROM t_shirts",
    "SQLResult": "[(Decimal('180850'),)]",
    "Answer": "The total undiscounted value of all t-shirts in inventory is ₹180,850."
    },
    
    {
    "Question": "What would be the total revenue from all Levi t-shirts with current discounts?",
    "SQLQuery": "SELECT SUM(t.price * t.stock_quantity * (100 - COALESCE(d.pct_discount, 0)) / 100) AS discounted_revenue FROM t_shirts t LEFT JOIN discounts d ON t.t_shirt_id = d.t_shirt_id WHERE t.brand = 'Levi'",
    "SQLResult": "[(Decimal('31098.00'),)]",
    "Answer": "The total revenue from all Levi t-shirts with current discounts applied would be ₹31,098."
    }
]