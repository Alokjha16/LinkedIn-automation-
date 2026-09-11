from src.resume_customizer import customize_resume

post_text = """
Looking for Java Developer with Spring Boot, Microservices, AWS, SQL,
REST API, Docker and Git experience.
"""

pdf_path = customize_resume(post_text, 1)

print("Resume created:", pdf_path)