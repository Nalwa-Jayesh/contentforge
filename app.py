import streamlit as st
import json
from datetime import datetime
from workflow.publication_workflow import PublicationWorkflow
from models.content_models import ContentStatus, AgentType
import plotly.express as px
import pandas as pd
from utils.human_feedback import HumanFeedback

# Initialize workflow
workflow = PublicationWorkflow()
human_feedback_util = HumanFeedback()

def format_datetime(dt_str):
    """Format datetime string for display"""
    return datetime.fromisoformat(dt_str).strftime("%Y-%m-%d %H:%M:%S")

def display_feedback_form():
    """Displays the form for providing human feedback."""
    if 'current_review_session' in st.session_state and st.session_state.current_review_session:
        session = st.session_state.current_review_session
        review_id = session['review_id']
        
        st.subheader(f"✍️ Provide Feedback for Review {review_id[:8]}...")
        st.info(f"Chapter ID: {session['chapter_id']} | Review Type: {session['review_type']}")
        
        st.write("---")
        st.write("#### Original Content Preview:")
        st.markdown(session['content'])
        st.write("---")

        # Get feedback template
        template = human_feedback_util.format_feedback_template(session['review_type'])

        updated_content_key = f"updated_content_form_{review_id}"
        reviewer_notes_key = f"reviewer_notes_form_{review_id}"

        # Use the content from the session as the default for updated_content
        updated_content = st.text_area(
            "Updated Content (edit directly here if needed)",
            value=session['content'],
            height=300,
            key=updated_content_key
        )
        
        reviewer_notes = st.text_area(
            "Reviewer Notes/Feedback",
            value=template,
            height=200,
            key=reviewer_notes_key
        )

        col_comp, col_rej = st.columns(2)
        with col_comp:
            if st.button("Complete Review", key=f"complete_form_{review_id}"):
                result = human_feedback_util.provide_feedback(
                    feedback=reviewer_notes,
                    updated_content=updated_content
                )
                if result['success']:
                    st.success("Feedback successfully submitted!")
                    st.session_state.current_review_session = None # Clear session
                    st.rerun()
                else:
                    st.error(f"Failed to submit feedback: {result.get('error', 'Unknown error')}")
        with col_rej:
            if st.button("Reject Review", key=f"reject_form_{review_id}"):
                result = human_feedback_util.cancel_review(
                    review_id=review_id,
                    reason=reviewer_notes if reviewer_notes != template else "No specific reason provided."
                )
                if result:
                    st.warning("Review rejected and sent back for revision.")
                    st.session_state.current_review_session = None # Clear session
                    st.rerun()
                else:
                    st.error("Failed to reject review.")
    else:
        st.info("Select a pending review to start providing feedback.")
    st.write("---") # Separator below the form


def display_review_dashboard():
    """Display the reviewer dashboard"""
    st.subheader("👥 Reviewer Dashboard")
    
    # Get reviewer dashboard data
    dashboard = workflow.human_interface.get_reviewer_dashboard()
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Pending Reviews", dashboard['review_metrics']['pending_count'])
    with col2:
        st.metric("Completed Today", dashboard['review_metrics']['completed_today'])
    with col3:
        st.metric("Avg Review Time", dashboard['review_metrics']['average_review_time'])
    with col4:
        st.metric("Most Common Type", dashboard['review_metrics']['most_common_review_type'])
    
    # Display pending reviews
    st.subheader("📝 Pending Reviews")
    # Check if there's an active session from the dashboard
    if 'current_review_session' in st.session_state and st.session_state.current_review_session:
        st.info(f"Currently reviewing: {st.session_state.current_review_session['review_id'][:8]}...")
    
    for review in dashboard['pending_reviews']:
        with st.expander(f"Review {review['review_id'][:8]} - {review['review_type']} ({review['urgency']} priority)"):
            st.write(f"Chapter ID: {review['chapter_id']}")
            st.write(f"Submitted: {format_datetime(review['submitted_at'])}")
            st.write(f"Content Length: {review['content_length']} characters")
            
            # Add review actions
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Start Review", key=f"start_{review['review_id']}"):
                    st.session_state.current_review_session = human_feedback_util.start_review_session(review['review_id'])
                    st.rerun()
            with col2:
                if st.button("Reject Review", key=f"reject_{review['review_id']}"):
                    # Prompt for reason if not provided directly
                    reason = st.text_input("Reason for Rejection", key=f"reason_{review['review_id']}")
                    if st.button("Confirm Rejection", key=f"confirm_reject_{review['review_id']}"):
                        success = human_feedback_util.cancel_review(review['review_id'], reason)
                        if success:
                            st.success("Review rejected")
                            st.rerun()
                        else:
                            st.error("Failed to reject review.")
    
    # Display recent completions
    st.subheader("✅ Recent Completions")
    for review in dashboard['recent_completions']:
        with st.expander(f"Review {review['review_id'][:8]} - {review['review_type']}"):
            st.write(f"Chapter ID: {review['chapter_id']}")
            st.write(f"Completed: {format_datetime(review['completed_at'])}")
            st.write(f"Feedback Length: {review['feedback_length']} characters")

def display_publication_viewer():
    """Display the publication viewer"""
    st.subheader("📚 Publication Viewer")
    
    # Get the latest publication version
    publication_version = workflow.version_manager.get_latest_version(
        chapter_id="PUBLICATION",
        status=ContentStatus.PUBLISHED
    )
    
    if not publication_version:
        st.warning("No published content found")
        return
    
    # Parse the publication content
    publication_data = json.loads(publication_version.content)
    
    # Display metadata
    st.write("### Publication Details")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Chapters", publication_data['metadata'].get('total_chapters', 0))
        st.metric("Generation Date", format_datetime(publication_data['metadata'].get('generation_date', '')))
    with col2:
        st.metric("Publication Type", publication_data['metadata'].get('publication_type', 'book'))
        if 'workflow_stats' in publication_data['metadata']:
            stats = publication_data['metadata']['workflow_stats']
            st.metric("Success Rate", f"{stats.get('completed_chapters', 0)}/{stats.get('total_chapters', 0)}")
    
    # Display chapters
    st.write("### Chapters")
    search_query = st.text_input("🔍 Search in chapters", "")
    
    # Filter chapters based on search
    filtered_chapters = publication_data['chapters']
    if search_query:
        filtered_chapters = [
            chapter for chapter in filtered_chapters
            if search_query.lower() in chapter['title'].lower() or 
               search_query.lower() in chapter['content'].lower()
        ]
    
    # Display filtered chapters
    for i, chapter in enumerate(filtered_chapters, 1):
        with st.expander(f"Chapter {i}: {chapter['title']}", expanded=i==1):
            # Display chapter metadata
            if 'metadata' in chapter:
                st.caption("Chapter Metadata:")
                for key, value in chapter['metadata'].items():
                    st.text(f"{key}: {value}")
            
            # Display chapter content
            st.markdown(chapter['content'])
            
            # Add a download button for the chapter
            st.download_button(
                label="Download Chapter",
                data=chapter['content'],
                file_name=f"chapter_{i}_{chapter['title']}.txt",
                mime="text/plain"
            )

            # Human review feedback section
            human_review_id = chapter['metadata'].get('human_review_id')
            if human_review_id:
                st.subheader("Human Review Feedback")
                current_review_details = workflow.human_interface.get_review_details(human_review_id)

                if current_review_details and current_review_details['status'] == 'pending':
                    st.info(f"Review Status: {current_review_details['status'].capitalize()}")
                    st.write("Please provide your feedback and updated content.")

                    # Display original content for reference (optional, can be expanded)
                    with st.expander("View Original Content"):
                        st.markdown(current_review_details['version_info']['content_preview'])

                    updated_content = st.text_area(
                        "Updated Content (if any)",
                        value=current_review_details['version_info']['content_preview'],
                        height=300,
                        key=f"updated_content_{human_review_id}"
                    )
                    
                    # Pre-fill notes with a template based on review type
                    review_type = current_review_details.get('review_type', 'general')
                    template_notes = human_feedback_util.format_feedback_template(review_type)

                    reviewer_notes = st.text_area(
                        "Reviewer Notes/Feedback",
                        value=template_notes,
                        key=f"reviewer_notes_{human_review_id}"
                    )

                    col_comp, col_rej = st.columns(2)
                    with col_comp:
                        if st.button(f"Complete Review {human_review_id[:6]}...", key=f"complete_review_{human_review_id}"):
                            # Directly use the utility class for feedback
                            result = human_feedback_util.provide_feedback(
                                review_id=human_review_id,
                                updated_content=updated_content,
                                feedback=reviewer_notes
                            )
                            if result['success']:
                                st.success("Review completed and new version created!")
                                st.rerun()
                            else:
                                st.error(f"Failed to complete review: {result.get('error', 'Unknown error')}")
                    with col_rej:
                        if st.button(f"Reject Review {human_review_id[:6]}...", key=f"reject_review_{human_review_id}"):
                            # Directly use the utility class for cancellation
                            success = human_feedback_util.cancel_review(
                                review_id=human_review_id,
                                reason=reviewer_notes if reviewer_notes != template_notes else "No specific reason provided."
                            )
                            if success:
                                st.warning("Review rejected and sent back for revision.")
                                st.rerun()
                            else:
                                st.error("Failed to reject review.")
                elif current_review_details:
                    st.success(f"Review Status: {current_review_details['status'].capitalize()}")
                    if current_review_details['reviewer_notes']:
                        st.caption("Reviewer Notes:")
                        st.markdown(current_review_details['reviewer_notes'])

def main():
    st.set_page_config(
        page_title="AI Publication System",
        page_icon="📚",
        layout="wide"
    )
    
    st.title("📚 AI Publication System")
    
    # Sidebar navigation
    page = st.sidebar.selectbox(
        "Navigation",
        ["Reviewer Dashboard", "Publication Viewer"]
    )
    
    if page == "Reviewer Dashboard":
        # Display the review form if a session is active
        if 'current_review_session' in st.session_state and st.session_state.current_review_session:
            display_feedback_form()
        display_review_dashboard()
    else:
        display_publication_viewer()

if __name__ == "__main__":
    main() 