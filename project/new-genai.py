import streamlit as st
import os
from dotenv import load_dotenv
import json
import re
from datetime import datetime
import time
import matplotlib.pyplot as plt
import PyPDF2 as pdf
import google.generativeai as genai

# Load environment variables
load_dotenv()


# Configure the Gemini API with the API key
def configure_genai(api_key):
    genai.configure(api_key=api_key)


# Function to validate API key
def validate_api_key(api_key):
    try:
        configure_genai(api_key)
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content("Test")
        return True
    except Exception as e:
        st.error(f"API Key validation failed: {str(e)}")
        return False


# Function to get Gemini response
def get_gemini_response(input):
    model = genai.GenerativeModel('gemini-pro')
    with st.spinner("Analyzing..."):
        progress_bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            progress_bar.progress(i + 1)
        response = model.generate_content(input)
    return response.text


# Function to extract text from PDF
def input_pdf_text(uploaded_file):
    try:
        reader = pdf.PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return None


# Updated function to parse AI response
def parse_ai_response(response):
    response = response.strip()
    try:
        # Remove trailing commas from arrays
        response = re.sub(r',\s*]', ']', response)
        # First, try to parse the entire response as JSON
        parsed = json.loads(response)
    except json.JSONDecodeError:
        # If that fails, try to extract JSON from the response
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                # Remove trailing commas from arrays in the extracted JSON
                extracted_json = re.sub(r',\s*]', ']', match.group())
                parsed = json.loads(extracted_json)
            except json.JSONDecodeError as e:
                st.error(f"JSON parsing error in extracted content: {str(e)}")
                st.error("Raw response:")
                st.code(response)
                return None
        else:
            st.error("Could not find valid JSON in the response")
            st.error("Raw response:")
            st.code(response)
            return None

    # Convert percentage strings to floats
    for key in ['JD Match', 'TechnicalSkills', 'SoftSkills', 'Experience', 'Education', 'Projects', 'ATS_Score',
                'ATS_Compatibility_Score']:
        if key in parsed and isinstance(parsed[key], str):
            try:
                parsed[key] = float(parsed[key].rstrip('%'))
            except ValueError:
                st.warning(f"Could not convert {key} to float. Keeping as string.")

    return parsed


# Function to suggest improvements
def suggest_improvements(missing_keywords, job_description):
    prompt = f"""
    Given the following missing keywords from a resume and the job description, 
    provide specific suggestions on how to incorporate these keywords into the resume effectively. 
    Consider the context of the job description when making suggestions.

    Missing Keywords: {', '.join(missing_keywords)}

    Job Description:
    {job_description}

    Please provide detailed suggestions for each keyword, including:
    1. Where in the resume to add the keyword (e.g., skills section, work experience, etc.)
    2. How to phrase it naturally within the context of the resume
    3. If applicable, suggest a brief example of how to demonstrate experience with the keyword

    Format your response as a bulleted list for easy reading.
    """
    suggestions = get_gemini_response(prompt)
    return suggestions


# Function to create radar chart
def create_radar_chart(parsed_response):
    categories = ['Technical Skills', 'Soft Skills', 'Experience', 'Education', 'Projects']
    scores = []
    for category in categories:
        try:
            score = float(parsed_response.get(category.replace(' ', ''), 0))
            scores.append(score)
        except ValueError:
            st.warning(f"Invalid score for {category}. Using 0.")
            scores.append(0)

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(projection='polar'))
    ax.plot(categories, scores)
    ax.fill(categories, scores, alpha=0.25)
    plt.title('Resume Strength Analysis')
    return fig


# Updated function to add download button
def add_download_button(content, filename):
    st.download_button(
        label="Download Results",
        data=content,
        file_name=f"{filename}.txt",
        mime="text/plain"
    )


# Function for ATS Check - Resume Only
def ats_check_resume_only():
    st.subheader("ATS Check - Resume Only")
    uploaded_file = st.file_uploader("Upload Your Resume", type="pdf", key="resume_only")
    if uploaded_file is not None:
        text = input_pdf_text(uploaded_file)
        if text:
            if st.button("Analyze Resume", key="analyze_resume_only"):
                prompt = f"""
                Analyze this resume and provide:
                1. An overall ATS score (0-100)
                2. Strengths of the resume
                3. Areas for improvement
                4. Keyword analysis
                5. Formatting and structure assessment

                Resume:
                {text}

                Provide the response in the following JSON format:
                {{
                    "ATS_Score": <score>,
                    "Strengths": ["<strength1>", "<strength2>", ...],
                    "Improvements": ["<improvement1>", "<improvement2>", ...],
                    "Keywords": ["<keyword1>", "<keyword2>", ...],
                    "Formatting": "<formatting_assessment>"
                }}
                """
                response = get_gemini_response(prompt)
                parsed_response = parse_ai_response(response)
                if parsed_response:
                    st.subheader("ATS Analysis Results")
                    st.metric("ATS Score", f"{parsed_response['ATS_Score']}/100")
                    st.subheader("Strengths")
                    for strength in parsed_response['Strengths']:
                        st.write(f"- {strength}")
                    st.subheader("Areas for Improvement")
                    for improvement in parsed_response['Improvements']:
                        st.write(f"- {improvement}")
                    st.subheader("Key Keywords Detected")
                    st.write(", ".join(parsed_response['Keywords']))
                    st.subheader("Formatting Assessment")
                    st.write(parsed_response['Formatting'])

                    # Add download button
                    add_download_button(json.dumps(parsed_response, indent=2), "ats_analysis_results")
                else:
                    st.error("Failed to parse the AI response. Please try again.")
        else:
            st.error("Failed to read the uploaded resume. Please try again.")
    else:
        st.info("Please upload a resume to proceed.")


# Updated Function for ATS Check with Job Description
def ats_check_with_jd():
    st.subheader("ATS Check - Resume with Job Description")
    uploaded_resume = st.file_uploader("Upload Your Resume", type="pdf", key="resume_with_jd")
    jd_text = st.text_area("Paste the Job Description here:", height=300)

    if uploaded_resume is not None and jd_text:
        resume_text = input_pdf_text(uploaded_resume)
        if resume_text:
            if st.button("Generate Analysis", key="generate_analysis"):
                prompt = f"""
                Analyze this resume against the job description and provide:
                1. An ATS compatibility score (0-100)
                2. Matched keywords between the resume and job description
                3. Missing keywords from the job description
                4. Suggestions for improvement
                5. Overall assessment of the resume's fit for the position

                Resume:
                {resume_text}

                Job Description:
                {jd_text}

                Provide the response in the following JSON format:
                {{
                    "ATS_Compatibility_Score": <score>,
                    "Matched_Keywords": ["<keyword1>", "<keyword2>", ...],
                    "Missing_Keywords": ["<keyword1>", "<keyword2>", ...],
                    "Improvement_Suggestions": ["<suggestion1>", "<suggestion2>", ...],
                    "Overall_Assessment": "<assessment_text>"
                }}
                """
                response = get_gemini_response(prompt)
                parsed_response = parse_ai_response(response)
                if parsed_response:
                    st.subheader("ATS Compatibility Analysis")
                    st.metric("ATS Compatibility Score", f"{parsed_response['ATS_Compatibility_Score']}/100")
                    st.subheader("Matched Keywords")
                    st.write(", ".join(parsed_response['Matched_Keywords']))
                    st.subheader("Missing Keywords")
                    st.write(", ".join(parsed_response['Missing_Keywords']))
                    st.subheader("Suggestions for Improvement")
                    for suggestion in parsed_response['Improvement_Suggestions']:
                        st.write(f"- {suggestion}")
                    st.subheader("Overall Assessment")
                    st.write(parsed_response['Overall_Assessment'])

                    # Add download button
                    add_download_button(json.dumps(parsed_response, indent=2), "ats_compatibility_analysis")
                else:
                    st.error("Failed to parse the AI response. Please try again.")
        else:
            st.error("Failed to read the uploaded resume. Please try again.")
    else:
        st.info("Please upload a resume and paste the job description to proceed.")


# Function for Real-time Content Suggestions
def real_time_suggestions():
    st.subheader("Real-time Content Suggestions")
    content = st.text_area("Enter your resume or cover letter content:")
    if st.button("Get Suggestions", key="get_suggestions"):
        prompt = f"""
        Provide real-time suggestions for improving this resume or cover letter content:

        Content:
        {content}

        Please provide suggestions for:
        1. Improving clarity and conciseness
        2. Enhancing the impact of achievements
        3. Optimizing for ATS systems
        4. Addressing any grammatical or structural issues

        Format your response as a bulleted list for easy reading.
        """
        response = get_gemini_response(prompt)
        st.subheader("Improvement Suggestions")
        st.write(response)

        # Add download button
        add_download_button(response, "content_suggestions")


# Function to Generate Resume/Cover Letter
def generate_resume_cover_letter():
    st.subheader("Generate Resume/Cover Letter")

    uploaded_resume = st.file_uploader("Upload Your Current Resume (Optional)", type="pdf", key="current_resume")
    jd = st.text_area("Enter the job description:", height=300)

    if st.button("Generate", key="generate_resume_cover_letter"):
        resume_text = ""
        if uploaded_resume is not None:
            resume_text = input_pdf_text(uploaded_resume)

        prompt = f"""
        Generate a tailored resume and cover letter based on the following information:

        Job Description:
        {jd}

        {"" if not resume_text else f"Current Resume: {resume_text}"}

        Please provide:
        1. A bullet-point outline for a tailored resume
        2. A draft cover letter

        {"If a current resume is provided, use it as a base and suggest improvements to tailor it to the job description." if resume_text else "Create a new resume outline based on the job description."}

        Format your response as follows:

        Resume Outline:
        - [Section 1]
          - [Bullet point 1]
          - [Bullet point 2]
        - [Section 2]
          - [Bullet point 1]
          - [Bullet point 2]

        Cover Letter:
        [Cover letter text]
        """
        response = get_gemini_response(prompt)
        st.subheader("Generated Content")
        st.write(response)

        # Add download button
        add_download_button(response, "generated_resume_cover_letter")


# Function to Analyze Job Description
def analyze_job_description():
    st.subheader("Job Description Analysis")
    jd = st.text_area("Enter the job description:")
    if st.button("Analyze", key="analyze_job_description"):
        prompt = f"""
        Analyze this job description and extract:
        1. Essential skills required
        2. Key qualifications
        3. Main responsibilities
        4. Company culture indicators
        5. Potential keywords for resume optimization

        Job Description:
        {jd}

        Provide the response in the following JSON format:
        {{
            "Essential_Skills": ["<skill1>", "<skill2>", ...],
            "Key_Qualifications": ["<qualification1>", "<qualification2>", ...],
            "Main_Responsibilities": ["<responsibility1>", "<responsibility2>", ...],
            "Company_Culture": ["<indicator1>", "<indicator2>", ...],
            "Resume_Keywords": ["<keyword1>", "<keyword2>", ...]
        }}
        """
        response = get_gemini_response(prompt)
        parsed_response = parse_ai_response(response)
        if parsed_response:
            st.subheader("Job Description Analysis Results")
            st.subheader("Essential Skills")
            for skill in parsed_response['Essential_Skills']:
                st.write(f"- {skill}")
            st.subheader("Key Qualifications")
            for qual in parsed_response['Key_Qualifications']:
                st.write(f"- {qual}")
            st.subheader("Main Responsibilities")
            for resp in parsed_response['Main_Responsibilities']:
                st.write(f"- {resp}")
            st.subheader("Company Culture Indicators")
            for indicator in parsed_response['Company_Culture']:
                st.write(f"- {indicator}")
            st.subheader("Potential Resume Keywords")
            st.write(", ".join(parsed_response['Resume_Keywords']))

            # Add download button
            add_download_button(json.dumps(parsed_response, indent=2), "job_description_analysis")
        else:
            st.error("Failed to parse the AI response. Please try again.")


# Function to get company information (excluding recent news and achievements)
def get_company_info():
    st.subheader("Company Information for Interview Preparation")
    company_name = st.text_input("Enter the name of the company:")
    if st.button("Get Company Info", key="get_company_info"):
        prompt = f"""
Provide detailed information about {company_name} that would be helpful for a job interview. Include:
1. Brief company history
2. Main products or services
3. Company culture and values
4. Key competitors

Format the response in a clear, easy-to-read structure with headings for each section.
"""
        response = get_gemini_response(prompt)
        st.subheader(f"Information about {company_name}")
        st.write(response)

        # Add download button
        add_download_button(response, f"{company_name}_info")


# Updated function for LinkedIn Optimization
def linkedin_optimization():
    st.subheader("AI-Powered LinkedIn Optimization")
    uploaded_file = st.file_uploader("Upload Your LinkedIn Profile PDF", type="pdf", key="linkedin_profile")

    if uploaded_file is not None:
        profile_text = input_pdf_text(uploaded_file)
        if profile_text:
            if st.button("Analyze LinkedIn Profile", key="analyze_linkedin"):
                prompt = f"""
                Analyze this LinkedIn profile and provide:
                1. An overall profile strength score (0-100)
                2. Strengths of the profile
                3. Areas for improvement
                4. Suggestions for enhancing visibility and reach
                5. Keyword optimization recommendations
                6. Content ideas for posts or articles

                LinkedIn Profile:
                {profile_text}

                Provide the response in the following JSON format:
                {{
                    "Profile_Strength": <score>,
                    "Strengths": ["<strength1>", "<strength2>", ...],
                    "Improvements": ["<improvement1>", "<improvement2>", ...],
                    "Visibility_Suggestions": ["<suggestion1>", "<suggestion2>", ...],
                    "Keyword_Recommendations": ["<keyword1>", "<keyword2>", ...],
                    "Content_Ideas": ["<idea1>", "<idea2>", ...]
                }}
                """
                with st.spinner("Analyzing your LinkedIn profile..."):
                    response = get_gemini_response(prompt)
                    parsed_response = parse_ai_response(response)

                    if parsed_response:
                        st.subheader("LinkedIn Profile Analysis Results")
                        st.metric("Profile Strength", f"{parsed_response['Profile_Strength']}/100")

                        st.subheader("Strengths")
                        for strength in parsed_response['Strengths']:
                            st.write(f"- {strength}")

                        st.subheader("Areas for Improvement")
                        for improvement in parsed_response['Improvements']:
                            st.write(f"- {improvement}")

                        st.subheader("Visibility Enhancement Suggestions")
                        for suggestion in parsed_response['Visibility_Suggestions']:
                            st.write(f"- {suggestion}")

                        st.subheader("Keyword Optimization Recommendations")
                        st.write(", ".join(parsed_response['Keyword_Recommendations']))

                        st.subheader("Content Ideas for Posts or Articles")
                        for idea in parsed_response['Content_Ideas']:
                            st.write(f"- {idea}")

                        # Add download button
                        add_download_button(json.dumps(parsed_response, indent=2), "linkedin_profile_analysis")
                    else:
                        st.error("Failed to parse the AI response. Please try again.")
        else:
            st.error("Failed to read the uploaded LinkedIn profile PDF. Please try again.")
    else:
        st.info("Please upload your LinkedIn profile PDF to proceed.")


# Updated function for Interview Preparation
def interview_preparation():
    st.subheader("Interview Preparation")

    uploaded_resume = st.file_uploader("Upload Your Resume", type="pdf", key="interview_prep_resume")
    jd_text = st.text_area("Paste the Job Description here:", height=300)

    if uploaded_resume is not None and jd_text:
        resume_text = input_pdf_text(uploaded_resume)
        if resume_text:
            if st.button("Generate Interview Questions and Suggestions", key="generate_interview_prep"):
                prompt = f"""
                Based on the following job description and resume, please:
                1. Generate 10 likely interview questions
                2. For each question, provide a suggested answer using the STAR (Situation, Task, Action, Result) method
                3. Offer additional tips for answering each question effectively

                Job Description:
                {jd_text}

                Resume:
                {resume_text}

                Provide the response in the following JSON format:
                {{
                    "Interview_Questions": [
                        {{
                            "Question": "<question1>",
                            "STAR_Answer": {{
                                "Situation": "<situation>",
                                "Task": "<task>",
                                "Action": "<action>",
                                "Result": "<result>"
                            }},
                            "Additional_Tips": ["<tip1>", "<tip2>", ...]
                        }},
                        ...
                    ]
                }}
                """
                response = get_gemini_response(prompt)
                parsed_response = parse_ai_response(response)

                if parsed_response:
                    st.subheader("Interview Preparation Guide")
                    for i, qa in enumerate(parsed_response['Interview_Questions'], 1):
                        st.markdown(f"### Question {i}: {qa['Question']}")
                        st.markdown("#### Suggested STAR Answer:")
                        st.markdown(f"**Situation:** {qa['STAR_Answer']['Situation']}")
                        st.markdown(f"**Task:** {qa['STAR_Answer']['Task']}")
                        st.markdown(f"**Action:** {qa['STAR_Answer']['Action']}")
                        st.markdown(f"**Result:** {qa['STAR_Answer']['Result']}")
                        st.markdown("#### Additional Tips:")
                        for tip in qa['Additional_Tips']:
                            st.markdown(f"- {tip}")
                        st.markdown("---")

                    # Add download button
                    add_download_button(json.dumps(parsed_response, indent=2), "interview_preparation_guide")
                else:
                    st.error("Failed to parse the AI response. Please try again.")
        else:
            st.error("Failed to read the uploaded resume. Please try again.")
    else:
        st.info("Please upload your resume and paste the job description to proceed.")


# New function for Skill Gap Analysis and Courses Recommendation
def skill_gap_analysis():
    st.subheader("Skill Gap Analysis and Courses Recommendation")

    uploaded_resume = st.file_uploader("Upload Your Resume", type="pdf", key="skill_gap_resume")
    jd_text = st.text_area("Paste the Job Description here:", height=300)

    if uploaded_resume is not None and jd_text:
        resume_text = input_pdf_text(uploaded_resume)
        if resume_text:
            if st.button("Analyze Skill Gap and Recommend Courses", key="analyze_skill_gap"):
                prompt = f"""
                Based on the following resume and job description, please:
                1. Identify the skills present in the resume
                2. Identify the skills required by the job description
                3. Determine the skill gaps (skills required but not present in the resume)
                4. For each skill gap, recommend an online course or resource to learn that skill

                Resume:
                {resume_text}

                Job Description:
                {jd_text}

                Provide the response in the following JSON format:
                {{
                    "Skills_in_Resume": ["<skill1>", "<skill2>", ...],
                    "Skills_Required": ["<skill1>", "<skill2>", ...],
                    "Skill_Gaps": [
                        {{
                            "Skill": "<skill1>",
                            "Course_Recommendation": {{
                                "Course_Name": "<course_name>",
                                "Provider": "<provider>"
                            }}
                        }},
                        ...
                    ]
                }}
                """
                response = get_gemini_response(prompt)
                parsed_response = parse_ai_response(response)

                if parsed_response:
                    st.subheader("Skill Gap Analysis Results")

                    st.markdown("### Skills in Your Resume")
                    for skill in parsed_response['Skills_in_Resume']:
                        st.write(f"- {skill}")

                    st.markdown("### Skills Required for the Job")
                    for skill in parsed_response['Skills_Required']:
                        st.write(f"- {skill}")

                    st.markdown("### Skill Gaps and Course Recommendations")
                    for gap in parsed_response['Skill_Gaps']:
                        st.markdown(f"**{gap['Skill']}**")
                        st.markdown(f"Recommended Course: {gap['Course_Recommendation']['Course_Name']}")
                        st.markdown(f"Available at: {gap['Course_Recommendation']['Provider']}")
                        st.markdown("---")

                    # Add download button
                    add_download_button(json.dumps(parsed_response, indent=2), "skill_gap_analysis")
                else:
                    st.error("Failed to parse the AI response. Please try again.")
        else:
            st.error("Failed to read the uploaded resume. Please try again.")
    else:
        st.info("Please upload your resume and paste the job description to proceed.")


# Main Streamlit app
def main():
    st.set_page_config(page_title="AI Resume Coach", page_icon="📄", layout="wide")

    if 'api_key' not in st.session_state:
        st.session_state.api_key = ''

    if not st.session_state.api_key:
        st.markdown("## 🔑 API Key Verification")
        api_key = st.text_input("Enter your Google Generative AI Gemini API Key:", type="password")
        if st.button("Validate API Key"):
            if validate_api_key(api_key):
                st.session_state.api_key = api_key
                st.success("✅ API Key validated successfully!")
                st.rerun()
            else:
                st.error("❌ Invalid API Key. Please try again.")
    else:
        configure_genai(st.session_state.api_key)
        st.title("📄 AI Resume Coach")
        st.markdown("### Elevate Your Resume's ATS Performance with AI-Driven Insights")

        features = [
            {"value": "ats-resume", "label": "ATS Check - Resume Only"},
            {"value": "ats-resume-jd", "label": "ATS Check - Resume with Job Description"},
            {"value": "real-time-suggestions", "label": "Real-time Content Suggestions"},
            {"value": "generate-resume", "label": "Generate Resume/Cover Letter"},
            {"value": "analyze-jd", "label": "Job Description Analysis"},
            {"value": "company-info", "label": "Company Information for Interview Prep"},
            {"value": "linkedin-optimization", "label": "AI-Powered LinkedIn Optimization"},
            {"value": "interview-preparation", "label": "Interview Preparation"},
            {"value": "skill-gap-analysis", "label": "Skill Gap Analysis and Courses Recommendation"}
        ]

        selected_feature = st.selectbox("Select a feature", options=[f["label"] for f in features],
                                        format_func=lambda x: x)

        if selected_feature:
            feature_value = next(f["value"] for f in features if f["label"] == selected_feature)
            if feature_value == "ats-resume":
                ats_check_resume_only()
            elif feature_value == "ats-resume-jd":
                ats_check_with_jd()
            elif feature_value == "real-time-suggestions":
                real_time_suggestions()
            elif feature_value == "generate-resume":
                generate_resume_cover_letter()
            elif feature_value == "analyze-jd":
                analyze_job_description()
            elif feature_value == "company-info":
                get_company_info()
            elif feature_value == "linkedin-optimization":
                linkedin_optimization()
            elif feature_value == "interview-preparation":
                interview_preparation()
            elif feature_value == "skill-gap-analysis":
                skill_gap_analysis()


if __name__ == "__main__":
    main()
