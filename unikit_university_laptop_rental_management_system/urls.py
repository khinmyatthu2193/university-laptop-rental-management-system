from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static


def home(request):
    return HttpResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>UniKit System</title>
        <!-- Font Awesome for Icons -->
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            :root {
              --primary-navy: #1a237e;
              --action-blue: #2196f3;
              --accent-gold: #ffc107;
              --background-white: #ffffff;
              --light-bg: #f5f7fa;
            }

            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 0; 
                background: var(--light-bg); 
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
            }

            .container { 
                max-width: 800px; 
                margin: 50px auto; 
                background: var(--background-white); 
                padding: 40px; 
                border-radius: 15px; 
                box-shadow: 0 10px 30px rgba(26, 35, 126, 0.1); 
                text-align: center;
                border-top: 5px solid var(--primary-navy);
            }
            
            /* Logo Styling */
            .logo-section {
                margin-bottom: 25px;
            }
            
            .logo-section img {
                max-width: 180px;
                height: auto;
            }

            h1 { 
                color: var(--primary-navy); 
                text-align: center; 
                font-weight: 700;
                margin-bottom: 5px;
            }
            
            p.subtitle {
                color: var(--action-blue);
                text-align: center;
                font-weight: 600;
                margin-bottom: 30px;
                letter-spacing: 1px;
            }

            .success { 
                background: linear-gradient(135deg, var(--primary-navy), #283593);
                color: white; 
                padding: 20px; 
                border-radius: 10px; 
                text-align: center; 
                margin: 30px 0; 
                border-left: 5px solid var(--accent-gold);
                font-size: 1.1rem;
            }
            
            .success i {
                color: var(--accent-gold);
                margin-right: 10px;
            }

            .menu { text-align: center; margin: 40px 0; }
            
            .menu a { 
                display: inline-block; 
                margin: 10px; 
                padding: 14px 35px; 
                background: var(--action-blue); 
                color: white; 
                text-decoration: none; 
                border-radius: 30px; 
                font-weight: bold; 
                transition: all 0.3s;
                box-shadow: 0 4px 6px rgba(33, 150, 243, 0.2);
            }
            
            .menu a:hover { 
                background: var(--primary-navy); 
                transform: translateY(-3px);
                box-shadow: 0 6px 12px rgba(26, 35, 126, 0.2);
            }

            ul.features {
                list-style: none;
                padding: 0;
                text-align: left;
                max-width: 500px;
                margin: 0 auto;
                color: #555;
            }

            ul.features li {
                padding: 10px 0;
                border-bottom: 1px solid #eee;
                display: flex;
                align-items: center;
            }
            
            ul.features li i {
                color: var(--accent-gold);
                width: 30px;
                font-size: 1.2rem;
            }

            .footer {
                margin-top: 40px;
                border-top: 1px solid #eee;
                padding-top: 20px;
                color: #999;
                font-size: 0.85rem;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <!-- MIIT Logo -->
            <div class="logo-section">
                <img src="https://z-cdn-media.chatglm.cn/files/fae133c4-5e02-47d5-a68f-16d4f95385c3.png?auth_key=1870050463-2c00c6f6ae7f4e9b978eb61548e7008b-0-905956e785ea81176b0278cfd8737a79" alt="MIIT Logo">
            </div>

            <h1>MIIT</h1>
            <p class="subtitle">University Laptop Rental Management System</p>
            
            <div class="success">
                <i class="fas fa-check-circle"></i> System Operational Successfully
            </div>
            
            <div class="menu">
                <!-- Changed 'Login to Admin' to 'Dashboard' to point to your app -->
                <a href="/home/login/"><i class="fas fa-home"></i> Log In</a>
            </div>
            
            <h3 style="color: var(--primary-navy);">System Features:</h3>
            <ul class="features">
                <li><i class="fas fa-laptop"></i> Laptop Inventory Management</li>
                <li><i class="fas fa-user-graduate"></i> Student Registration</li>
                <li><i class="fas fa-hand-holding"></i> Rental System</li>
                <li><i class="fas fa-file-invoice-dollar"></i> Replacing Processing</li>
                <li><i class="fas fa-tools"></i> Maintenance Tracking</li>
                <li><i class="fas fa-chart-line"></i> Analytics & Reports</li>
            </ul>
            
            <div class="footer">
                <p>&copy; 2026 Myanmar Institute of Information Technology. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """)

urlpatterns = [
    path('admin/', admin.site.urls),
    # This is the Landing Page (Root URL) - Uses the function above
    path('', home, name='landing_page'), 
    
    # This is your actual App - Moved to /home/ to avoid conflict
    path('home/', include('rental_system.urls')),  
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)