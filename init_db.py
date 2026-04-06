from main import app, db, Product

with app.app_context():
    db.create_all()

    # Add sample products if they don't exist
    if not Product.query.first():
        products = [
            Product(
                name='Cat Ear Headband',
                description='Soft cat ear accessory for a playful look.',
                price=19.99,
                images='["catears.jpg"]',
                is_featured=True
            ),
            Product(
                name='Keila Top',
                description='Comfortable handmade top with a stylish finish.',
                price=29.99,
                images='["keilatop.jpg"]',
                is_featured=True
            ),
            Product(
                name='Custom Keychains',
                description='Handmade keychains perfect for gifting.',
                price=39.99,
                images='["keychains.jpg"]',
                is_featured=True
            ),
        ]
        for product in products:
            db.session.add(product)
        db.session.commit()
        print('Sample products added!')
    else:
        print('Products already exist!')