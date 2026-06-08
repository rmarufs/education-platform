"""Furuzon live schema baseline.

Revision ID: 20260608_furuzon_baseline
Revises: 
Create Date: 2026-06-08
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260608_furuzon_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BASELINE_SQL = r"""
--
-- PostgreSQL database dump
--


-- Dumped from database version 15.17 (Homebrew)
-- Dumped by pg_dump version 15.17 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--



--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--



--
-- Name: userrole; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.userrole AS ENUM (
    'student',
    'teacher',
    'teacher_pending',
    'admin',
    'organization'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: answers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.answers (
    id integer NOT NULL,
    question_id integer NOT NULL,
    answer_text character varying(500) NOT NULL,
    is_correct boolean NOT NULL
);


--
-- Name: answers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.answers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: answers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.answers_id_seq OWNED BY public.answers.id;


--
-- Name: categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories (
    id integer NOT NULL,
    name character varying(100) NOT NULL
);


--
-- Name: categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categories_id_seq OWNED BY public.categories.id;


--
-- Name: comments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comments (
    id integer NOT NULL,
    lesson_id integer NOT NULL,
    user_id integer NOT NULL,
    text text NOT NULL,
    parent_comment_id integer,
    created_at timestamp without time zone
);


--
-- Name: comments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.comments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: comments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.comments_id_seq OWNED BY public.comments.id;


--
-- Name: contact_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contact_messages (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    email character varying(150) NOT NULL,
    subject character varying(200) NOT NULL,
    message text NOT NULL,
    created_at timestamp without time zone
);


--
-- Name: contact_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contact_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contact_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_messages_id_seq OWNED BY public.contact_messages.id;


--
-- Name: courses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.courses (
    id integer NOT NULL,
    title character varying(200) NOT NULL,
    description text,
    level character varying(50),
    teacher_id integer NOT NULL,
    category_id integer,
    rating double precision,
    created_at timestamp without time zone,
    image character varying(500),
    quiz_url character varying(500),
    is_guest_accessible boolean DEFAULT false NOT NULL
);


--
-- Name: courses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.courses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: courses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.courses_id_seq OWNED BY public.courses.id;


--
-- Name: group_homework_notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_homework_notifications (
    id integer NOT NULL,
    homework_id integer NOT NULL,
    student_id integer NOT NULL,
    notification_type character varying(50) DEFAULT 'new_homework'::character varying NOT NULL,
    read_at timestamp without time zone,
    created_at timestamp without time zone
);


--
-- Name: group_homework_notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.group_homework_notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: group_homework_notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.group_homework_notifications_id_seq OWNED BY public.group_homework_notifications.id;


--
-- Name: group_homework_submissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_homework_submissions (
    id integer NOT NULL,
    homework_id integer NOT NULL,
    student_id integer NOT NULL,
    file_url character varying,
    file_type character varying(50),
    filename character varying(255),
    comment text,
    submitted_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    teacher_comment text,
    reviewed_at timestamp without time zone,
    reviewed_by_id integer,
    homework_reply_read_at timestamp without time zone
);


--
-- Name: group_homework_submissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.group_homework_submissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: group_homework_submissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.group_homework_submissions_id_seq OWNED BY public.group_homework_submissions.id;


--
-- Name: group_homeworks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_homeworks (
    id integer NOT NULL,
    group_id integer NOT NULL,
    lesson_id integer NOT NULL,
    title character varying(200),
    description text NOT NULL,
    material_url character varying,
    material_type character varying(50),
    material_filename character varying(255),
    deadline timestamp without time zone,
    created_by_id integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: group_homeworks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.group_homeworks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: group_homeworks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.group_homeworks_id_seq OWNED BY public.group_homeworks.id;


--
-- Name: group_journal_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_journal_entries (
    id integer NOT NULL,
    group_id integer NOT NULL,
    lesson_id integer NOT NULL,
    student_id integer NOT NULL,
    present boolean DEFAULT false NOT NULL,
    grade integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    score_percent integer,
    CONSTRAINT ck_group_journal_grade_range CHECK (((grade IS NULL) OR ((grade >= 1) AND (grade <= 5)))),
    CONSTRAINT ck_group_journal_score_percent_range CHECK (((score_percent IS NULL) OR ((score_percent >= 0) AND (score_percent <= 100))))
);


--
-- Name: group_journal_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.group_journal_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: group_journal_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.group_journal_entries_id_seq OWNED BY public.group_journal_entries.id;


--
-- Name: group_lesson_chat_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_lesson_chat_messages (
    id integer NOT NULL,
    group_id integer NOT NULL,
    lesson_id integer NOT NULL,
    user_id integer NOT NULL,
    text text NOT NULL,
    created_at timestamp without time zone NOT NULL,
    recipient_id integer,
    message_scope character varying(20) DEFAULT 'public'::character varying NOT NULL
);


--
-- Name: group_lesson_chat_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.group_lesson_chat_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: group_lesson_chat_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.group_lesson_chat_messages_id_seq OWNED BY public.group_lesson_chat_messages.id;


--
-- Name: group_lesson_progress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_lesson_progress (
    id integer NOT NULL,
    group_id integer NOT NULL,
    lesson_id integer NOT NULL,
    student_id integer NOT NULL,
    completed_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: group_lesson_progress_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.group_lesson_progress_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: group_lesson_progress_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.group_lesson_progress_id_seq OWNED BY public.group_lesson_progress.id;


--
-- Name: group_lesson_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_lesson_sessions (
    id integer NOT NULL,
    group_id integer NOT NULL,
    lesson_id integer NOT NULL,
    status character varying(20) DEFAULT 'not_started'::character varying NOT NULL,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    started_by_id integer,
    completed_by_id integer,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: group_lesson_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.group_lesson_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: group_lesson_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.group_lesson_sessions_id_seq OWNED BY public.group_lesson_sessions.id;


--
-- Name: group_lessons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_lessons (
    id integer NOT NULL,
    group_id integer NOT NULL,
    title character varying NOT NULL,
    description text,
    video_url character varying,
    "order" integer,
    created_at timestamp without time zone,
    cover_url character varying,
    group_module_id integer,
    quiz_url character varying(500)
);


--
-- Name: group_lessons_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.group_lessons_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: group_lessons_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.group_lessons_id_seq OWNED BY public.group_lessons.id;


--
-- Name: group_materials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_materials (
    id integer NOT NULL,
    lesson_id integer NOT NULL,
    title character varying NOT NULL,
    file_url character varying,
    created_at timestamp without time zone
);


--
-- Name: group_materials_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.group_materials_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: group_materials_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.group_materials_id_seq OWNED BY public.group_materials.id;


--
-- Name: group_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_members (
    id integer NOT NULL,
    group_id integer NOT NULL,
    student_id integer NOT NULL,
    grade integer,
    is_paid boolean,
    joined_at timestamp without time zone,
    payment_day integer DEFAULT 1,
    paid_until date,
    last_paid_at timestamp without time zone,
    CONSTRAINT ck_group_members_payment_day_range CHECK (((payment_day IS NULL) OR ((payment_day >= 1) AND (payment_day <= 31))))
);


--
-- Name: group_members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.group_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: group_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.group_members_id_seq OWNED BY public.group_members.id;


--
-- Name: group_modules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_modules (
    id integer NOT NULL,
    group_id integer NOT NULL,
    title character varying(200) NOT NULL,
    order_index integer DEFAULT 0 NOT NULL,
    quiz_url character varying(500)
);


--
-- Name: group_modules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.group_modules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: group_modules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.group_modules_id_seq OWNED BY public.group_modules.id;


--
-- Name: group_payment_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_payment_entries (
    id integer NOT NULL,
    group_id integer NOT NULL,
    student_id integer NOT NULL,
    month date NOT NULL,
    is_paid boolean DEFAULT false NOT NULL,
    paid_at timestamp without time zone,
    marked_by_id integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    payment_day integer,
    paid_until date,
    action character varying(50),
    CONSTRAINT ck_group_payment_entries_payment_day_range CHECK (((payment_day IS NULL) OR ((payment_day >= 1) AND (payment_day <= 31))))
);


--
-- Name: group_payment_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.group_payment_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: group_payment_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.group_payment_entries_id_seq OWNED BY public.group_payment_entries.id;


--
-- Name: groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.groups (
    id integer NOT NULL,
    name character varying NOT NULL,
    description text,
    organization_id integer NOT NULL,
    teacher_id integer,
    is_active boolean,
    created_at timestamp without time zone,
    avatar_url character varying,
    quiz_url character varying(500)
);


--
-- Name: groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.groups_id_seq OWNED BY public.groups.id;


--
-- Name: lessons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lessons (
    id integer NOT NULL,
    module_id integer NOT NULL,
    title character varying(200) NOT NULL,
    video_url character varying(500),
    description text,
    order_index integer NOT NULL,
    quiz_url character varying(500),
    cover_url character varying(500)
);


--
-- Name: lessons_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lessons_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lessons_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lessons_id_seq OWNED BY public.lessons.id;


--
-- Name: materials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.materials (
    id integer NOT NULL,
    lesson_id integer,
    course_id integer,
    title character varying(200),
    file_url character varying(500) NOT NULL,
    file_type character varying(20)
);


--
-- Name: materials_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.materials_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: materials_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.materials_id_seq OWNED BY public.materials.id;


--
-- Name: modules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.modules (
    id integer NOT NULL,
    course_id integer NOT NULL,
    title character varying(200) NOT NULL,
    order_index integer NOT NULL,
    description text,
    quiz_url character varying(500)
);


--
-- Name: modules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.modules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: modules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.modules_id_seq OWNED BY public.modules.id;


--
-- Name: organization_announcement_dismissals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organization_announcement_dismissals (
    id integer NOT NULL,
    announcement_id integer NOT NULL,
    user_id integer NOT NULL,
    dismissed_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: organization_announcement_dismissals_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.organization_announcement_dismissals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: organization_announcement_dismissals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.organization_announcement_dismissals_id_seq OWNED BY public.organization_announcement_dismissals.id;


--
-- Name: organization_announcements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organization_announcements (
    id integer NOT NULL,
    organization_id integer NOT NULL,
    title character varying(200) NOT NULL,
    body text NOT NULL,
    audience character varying(20) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by_id integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    expires_at timestamp without time zone
);


--
-- Name: organization_announcements_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.organization_announcements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: organization_announcements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.organization_announcements_id_seq OWNED BY public.organization_announcements.id;


--
-- Name: organization_students; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organization_students (
    id integer NOT NULL,
    organization_id integer,
    student_id integer,
    created_at timestamp without time zone,
    status character varying(20),
    was_removed_notification boolean,
    last_joined_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: organization_students_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.organization_students_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: organization_students_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.organization_students_id_seq OWNED BY public.organization_students.id;


--
-- Name: organization_teachers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organization_teachers (
    id integer NOT NULL,
    organization_id integer,
    teacher_id integer,
    status character varying,
    created_at timestamp without time zone,
    cover_letter text,
    attachment character varying(500),
    was_accepted_notification boolean DEFAULT false
);


--
-- Name: organization_teachers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.organization_teachers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: organization_teachers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.organization_teachers_id_seq OWNED BY public.organization_teachers.id;


--
-- Name: organizations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organizations (
    id integer NOT NULL,
    user_id integer,
    name character varying NOT NULL,
    description text,
    logo_url character varying,
    website character varying,
    created_at timestamp without time zone,
    phone character varying(50),
    status character varying(20),
    is_open boolean
);


--
-- Name: organizations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.organizations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: organizations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.organizations_id_seq OWNED BY public.organizations.id;


--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.password_reset_tokens (
    id integer NOT NULL,
    user_id integer NOT NULL,
    token_hash character varying(64) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    used_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    request_ip character varying(64),
    user_agent character varying(255)
);


--
-- Name: password_reset_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.password_reset_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: password_reset_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.password_reset_tokens_id_seq OWNED BY public.password_reset_tokens.id;


--
-- Name: progress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.progress (
    id integer NOT NULL,
    student_id integer NOT NULL,
    lesson_id integer NOT NULL,
    completed boolean NOT NULL,
    completed_at timestamp without time zone
);


--
-- Name: progress_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.progress_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: progress_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.progress_id_seq OWNED BY public.progress.id;


--
-- Name: push_subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.push_subscriptions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    endpoint character varying(500) NOT NULL,
    p256dh character varying(200) NOT NULL,
    auth character varying(200) NOT NULL,
    user_agent character varying(500),
    created_at timestamp without time zone
);


--
-- Name: push_subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.push_subscriptions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: push_subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.push_subscriptions_id_seq OWNED BY public.push_subscriptions.id;


--
-- Name: questions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.questions (
    id integer NOT NULL,
    quiz_id integer NOT NULL,
    question_text character varying(500) NOT NULL,
    question_type character varying(20),
    correct_text character varying(500)
);


--
-- Name: questions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.questions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: questions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.questions_id_seq OWNED BY public.questions.id;


--
-- Name: quiz_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quiz_attempts (
    id integer NOT NULL,
    quiz_id integer NOT NULL,
    student_id integer NOT NULL,
    correct integer NOT NULL,
    total integer NOT NULL,
    score integer NOT NULL,
    completed_at timestamp without time zone NOT NULL
);


--
-- Name: quiz_attempts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.quiz_attempts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: quiz_attempts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.quiz_attempts_id_seq OWNED BY public.quiz_attempts.id;


--
-- Name: quiz_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quiz_results (
    id integer NOT NULL,
    student_id integer NOT NULL,
    quiz_id integer NOT NULL,
    score integer NOT NULL,
    total integer NOT NULL,
    percentage integer NOT NULL,
    passed boolean NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: quiz_results_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.quiz_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: quiz_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.quiz_results_id_seq OWNED BY public.quiz_results.id;


--
-- Name: quizzes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quizzes (
    id integer NOT NULL,
    lesson_id integer,
    title character varying(200) NOT NULL,
    module_id integer,
    course_id integer,
    save_results boolean DEFAULT true NOT NULL
);


--
-- Name: quizzes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.quizzes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: quizzes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.quizzes_id_seq OWNED BY public.quizzes.id;


--
-- Name: reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reviews (
    id integer NOT NULL,
    course_id integer NOT NULL,
    student_id integer NOT NULL,
    rating integer NOT NULL,
    text text,
    created_at timestamp without time zone,
    teacher_id integer
);


--
-- Name: reviews_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reviews_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reviews_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reviews_id_seq OWNED BY public.reviews.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    email character varying(150) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role public.userrole NOT NULL,
    created_at timestamp without time zone,
    documents character varying(500),
    is_active boolean DEFAULT true,
    bio text,
    avatar_url character varying,
    birth_date date,
    phone_number character varying(32),
    parent_contact_name character varying(150),
    parent_contact_phone character varying(32),
    gender character varying(10)
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: vocabulary_attempt_answers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vocabulary_attempt_answers (
    id integer NOT NULL,
    attempt_id integer NOT NULL,
    item_id integer NOT NULL,
    student_answer text,
    is_correct boolean DEFAULT false NOT NULL
);


--
-- Name: vocabulary_attempt_answers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vocabulary_attempt_answers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vocabulary_attempt_answers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vocabulary_attempt_answers_id_seq OWNED BY public.vocabulary_attempt_answers.id;


--
-- Name: vocabulary_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vocabulary_attempts (
    id integer NOT NULL,
    vocab_set_id integer NOT NULL,
    student_id integer NOT NULL,
    score integer DEFAULT 0 NOT NULL,
    total integer DEFAULT 0 NOT NULL,
    lang_used character varying(10) DEFAULT 'ru'::character varying NOT NULL,
    completed_at timestamp without time zone DEFAULT now() NOT NULL,
    is_completed boolean DEFAULT false NOT NULL,
    retake_allowed boolean DEFAULT false NOT NULL,
    anti_cheat_flags_count integer DEFAULT 0 NOT NULL,
    anti_cheat_teacher_visible boolean DEFAULT false NOT NULL,
    anti_cheat_last_flag_at timestamp without time zone
);


--
-- Name: vocabulary_attempts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vocabulary_attempts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vocabulary_attempts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vocabulary_attempts_id_seq OWNED BY public.vocabulary_attempts.id;


--
-- Name: vocabulary_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vocabulary_items (
    id integer NOT NULL,
    vocab_set_id integer NOT NULL,
    "position" integer DEFAULT 0 NOT NULL,
    prompt_word character varying(512) NOT NULL,
    accepted_answers text,
    accepted_answers_ru text,
    accepted_answers_tj text
);


--
-- Name: vocabulary_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vocabulary_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vocabulary_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vocabulary_items_id_seq OWNED BY public.vocabulary_items.id;


--
-- Name: vocabulary_sets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vocabulary_sets (
    id integer NOT NULL,
    lesson_id integer NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    allow_retake boolean DEFAULT false NOT NULL
);


--
-- Name: vocabulary_sets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vocabulary_sets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vocabulary_sets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vocabulary_sets_id_seq OWNED BY public.vocabulary_sets.id;


--
-- Name: answers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.answers ALTER COLUMN id SET DEFAULT nextval('public.answers_id_seq'::regclass);


--
-- Name: categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories ALTER COLUMN id SET DEFAULT nextval('public.categories_id_seq'::regclass);


--
-- Name: comments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments ALTER COLUMN id SET DEFAULT nextval('public.comments_id_seq'::regclass);


--
-- Name: contact_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_messages ALTER COLUMN id SET DEFAULT nextval('public.contact_messages_id_seq'::regclass);


--
-- Name: courses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.courses ALTER COLUMN id SET DEFAULT nextval('public.courses_id_seq'::regclass);


--
-- Name: group_homework_notifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homework_notifications ALTER COLUMN id SET DEFAULT nextval('public.group_homework_notifications_id_seq'::regclass);


--
-- Name: group_homework_submissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homework_submissions ALTER COLUMN id SET DEFAULT nextval('public.group_homework_submissions_id_seq'::regclass);


--
-- Name: group_homeworks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homeworks ALTER COLUMN id SET DEFAULT nextval('public.group_homeworks_id_seq'::regclass);


--
-- Name: group_journal_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_journal_entries ALTER COLUMN id SET DEFAULT nextval('public.group_journal_entries_id_seq'::regclass);


--
-- Name: group_lesson_chat_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_chat_messages ALTER COLUMN id SET DEFAULT nextval('public.group_lesson_chat_messages_id_seq'::regclass);


--
-- Name: group_lesson_progress id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_progress ALTER COLUMN id SET DEFAULT nextval('public.group_lesson_progress_id_seq'::regclass);


--
-- Name: group_lesson_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_sessions ALTER COLUMN id SET DEFAULT nextval('public.group_lesson_sessions_id_seq'::regclass);


--
-- Name: group_lessons id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lessons ALTER COLUMN id SET DEFAULT nextval('public.group_lessons_id_seq'::regclass);


--
-- Name: group_materials id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_materials ALTER COLUMN id SET DEFAULT nextval('public.group_materials_id_seq'::regclass);


--
-- Name: group_members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_members ALTER COLUMN id SET DEFAULT nextval('public.group_members_id_seq'::regclass);


--
-- Name: group_modules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_modules ALTER COLUMN id SET DEFAULT nextval('public.group_modules_id_seq'::regclass);


--
-- Name: group_payment_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_payment_entries ALTER COLUMN id SET DEFAULT nextval('public.group_payment_entries_id_seq'::regclass);


--
-- Name: groups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.groups ALTER COLUMN id SET DEFAULT nextval('public.groups_id_seq'::regclass);


--
-- Name: lessons id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lessons ALTER COLUMN id SET DEFAULT nextval('public.lessons_id_seq'::regclass);


--
-- Name: materials id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.materials ALTER COLUMN id SET DEFAULT nextval('public.materials_id_seq'::regclass);


--
-- Name: modules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.modules ALTER COLUMN id SET DEFAULT nextval('public.modules_id_seq'::regclass);


--
-- Name: organization_announcement_dismissals id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_announcement_dismissals ALTER COLUMN id SET DEFAULT nextval('public.organization_announcement_dismissals_id_seq'::regclass);


--
-- Name: organization_announcements id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_announcements ALTER COLUMN id SET DEFAULT nextval('public.organization_announcements_id_seq'::regclass);


--
-- Name: organization_students id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_students ALTER COLUMN id SET DEFAULT nextval('public.organization_students_id_seq'::regclass);


--
-- Name: organization_teachers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_teachers ALTER COLUMN id SET DEFAULT nextval('public.organization_teachers_id_seq'::regclass);


--
-- Name: organizations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations ALTER COLUMN id SET DEFAULT nextval('public.organizations_id_seq'::regclass);


--
-- Name: password_reset_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens ALTER COLUMN id SET DEFAULT nextval('public.password_reset_tokens_id_seq'::regclass);


--
-- Name: progress id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.progress ALTER COLUMN id SET DEFAULT nextval('public.progress_id_seq'::regclass);


--
-- Name: push_subscriptions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions ALTER COLUMN id SET DEFAULT nextval('public.push_subscriptions_id_seq'::regclass);


--
-- Name: questions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.questions ALTER COLUMN id SET DEFAULT nextval('public.questions_id_seq'::regclass);


--
-- Name: quiz_attempts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts ALTER COLUMN id SET DEFAULT nextval('public.quiz_attempts_id_seq'::regclass);


--
-- Name: quiz_results id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_results ALTER COLUMN id SET DEFAULT nextval('public.quiz_results_id_seq'::regclass);


--
-- Name: quizzes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes ALTER COLUMN id SET DEFAULT nextval('public.quizzes_id_seq'::regclass);


--
-- Name: reviews id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews ALTER COLUMN id SET DEFAULT nextval('public.reviews_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: vocabulary_attempt_answers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_attempt_answers ALTER COLUMN id SET DEFAULT nextval('public.vocabulary_attempt_answers_id_seq'::regclass);


--
-- Name: vocabulary_attempts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_attempts ALTER COLUMN id SET DEFAULT nextval('public.vocabulary_attempts_id_seq'::regclass);


--
-- Name: vocabulary_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_items ALTER COLUMN id SET DEFAULT nextval('public.vocabulary_items_id_seq'::regclass);


--
-- Name: vocabulary_sets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_sets ALTER COLUMN id SET DEFAULT nextval('public.vocabulary_sets_id_seq'::regclass);


--
-- Name: answers answers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.answers
    ADD CONSTRAINT answers_pkey PRIMARY KEY (id);


--
-- Name: categories categories_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_name_key UNIQUE (name);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: comments comments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_pkey PRIMARY KEY (id);


--
-- Name: contact_messages contact_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_messages
    ADD CONSTRAINT contact_messages_pkey PRIMARY KEY (id);


--
-- Name: courses courses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.courses
    ADD CONSTRAINT courses_pkey PRIMARY KEY (id);


--
-- Name: group_homework_notifications group_homework_notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homework_notifications
    ADD CONSTRAINT group_homework_notifications_pkey PRIMARY KEY (id);


--
-- Name: group_homework_submissions group_homework_submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homework_submissions
    ADD CONSTRAINT group_homework_submissions_pkey PRIMARY KEY (id);


--
-- Name: group_homeworks group_homeworks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homeworks
    ADD CONSTRAINT group_homeworks_pkey PRIMARY KEY (id);


--
-- Name: group_journal_entries group_journal_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_journal_entries
    ADD CONSTRAINT group_journal_entries_pkey PRIMARY KEY (id);


--
-- Name: group_lesson_chat_messages group_lesson_chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_chat_messages
    ADD CONSTRAINT group_lesson_chat_messages_pkey PRIMARY KEY (id);


--
-- Name: group_lesson_progress group_lesson_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_progress
    ADD CONSTRAINT group_lesson_progress_pkey PRIMARY KEY (id);


--
-- Name: group_lesson_sessions group_lesson_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_sessions
    ADD CONSTRAINT group_lesson_sessions_pkey PRIMARY KEY (id);


--
-- Name: group_lessons group_lessons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lessons
    ADD CONSTRAINT group_lessons_pkey PRIMARY KEY (id);


--
-- Name: group_materials group_materials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_materials
    ADD CONSTRAINT group_materials_pkey PRIMARY KEY (id);


--
-- Name: group_members group_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_members
    ADD CONSTRAINT group_members_pkey PRIMARY KEY (id);


--
-- Name: group_modules group_modules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_modules
    ADD CONSTRAINT group_modules_pkey PRIMARY KEY (id);


--
-- Name: group_payment_entries group_payment_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_payment_entries
    ADD CONSTRAINT group_payment_entries_pkey PRIMARY KEY (id);


--
-- Name: groups groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_pkey PRIMARY KEY (id);


--
-- Name: lessons lessons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lessons
    ADD CONSTRAINT lessons_pkey PRIMARY KEY (id);


--
-- Name: materials materials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.materials
    ADD CONSTRAINT materials_pkey PRIMARY KEY (id);


--
-- Name: modules modules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.modules
    ADD CONSTRAINT modules_pkey PRIMARY KEY (id);


--
-- Name: organization_announcement_dismissals organization_announcement_dismissals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_announcement_dismissals
    ADD CONSTRAINT organization_announcement_dismissals_pkey PRIMARY KEY (id);


--
-- Name: organization_announcements organization_announcements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_announcements
    ADD CONSTRAINT organization_announcements_pkey PRIMARY KEY (id);


--
-- Name: organization_students organization_students_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_students
    ADD CONSTRAINT organization_students_pkey PRIMARY KEY (id);


--
-- Name: organization_teachers organization_teachers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_teachers
    ADD CONSTRAINT organization_teachers_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_user_id_key UNIQUE (user_id);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: progress progress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.progress
    ADD CONSTRAINT progress_pkey PRIMARY KEY (id);


--
-- Name: push_subscriptions push_subscriptions_endpoint_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_endpoint_key UNIQUE (endpoint);


--
-- Name: push_subscriptions push_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: questions questions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.questions
    ADD CONSTRAINT questions_pkey PRIMARY KEY (id);


--
-- Name: quiz_attempts quiz_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts
    ADD CONSTRAINT quiz_attempts_pkey PRIMARY KEY (id);


--
-- Name: quiz_results quiz_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_results
    ADD CONSTRAINT quiz_results_pkey PRIMARY KEY (id);


--
-- Name: quizzes quizzes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes
    ADD CONSTRAINT quizzes_pkey PRIMARY KEY (id);


--
-- Name: reviews reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_pkey PRIMARY KEY (id);


--
-- Name: organization_announcement_dismissals uq_announcement_user_dismissal; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_announcement_dismissals
    ADD CONSTRAINT uq_announcement_user_dismissal UNIQUE (announcement_id, user_id);


--
-- Name: group_homeworks uq_group_homework_lesson; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homeworks
    ADD CONSTRAINT uq_group_homework_lesson UNIQUE (group_id, lesson_id);


--
-- Name: group_homework_notifications uq_group_homework_notification_student; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homework_notifications
    ADD CONSTRAINT uq_group_homework_notification_student UNIQUE (homework_id, student_id, notification_type);


--
-- Name: group_homework_submissions uq_group_homework_submission_student; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homework_submissions
    ADD CONSTRAINT uq_group_homework_submission_student UNIQUE (homework_id, student_id);


--
-- Name: group_journal_entries uq_group_journal_entry; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_journal_entries
    ADD CONSTRAINT uq_group_journal_entry UNIQUE (group_id, lesson_id, student_id);


--
-- Name: group_lesson_progress uq_group_lesson_progress; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_progress
    ADD CONSTRAINT uq_group_lesson_progress UNIQUE (group_id, lesson_id, student_id);


--
-- Name: group_lesson_sessions uq_group_lesson_session; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_sessions
    ADD CONSTRAINT uq_group_lesson_session UNIQUE (group_id, lesson_id);


--
-- Name: group_payment_entries uq_group_payment_entry; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_payment_entries
    ADD CONSTRAINT uq_group_payment_entry UNIQUE (group_id, student_id, month);


--
-- Name: quiz_attempts uq_quiz_attempt_student; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts
    ADD CONSTRAINT uq_quiz_attempt_student UNIQUE (quiz_id, student_id);


--
-- Name: progress uq_student_lesson; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.progress
    ADD CONSTRAINT uq_student_lesson UNIQUE (student_id, lesson_id);


--
-- Name: organization_students uq_student_org; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_students
    ADD CONSTRAINT uq_student_org UNIQUE (student_id, organization_id);


--
-- Name: reviews uq_teacher_student_review; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT uq_teacher_student_review UNIQUE (teacher_id, student_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: vocabulary_attempt_answers vocabulary_attempt_answers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_attempt_answers
    ADD CONSTRAINT vocabulary_attempt_answers_pkey PRIMARY KEY (id);


--
-- Name: vocabulary_attempts vocabulary_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_attempts
    ADD CONSTRAINT vocabulary_attempts_pkey PRIMARY KEY (id);


--
-- Name: vocabulary_items vocabulary_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_items
    ADD CONSTRAINT vocabulary_items_pkey PRIMARY KEY (id);


--
-- Name: vocabulary_sets vocabulary_sets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_sets
    ADD CONSTRAINT vocabulary_sets_pkey PRIMARY KEY (id);


--
-- Name: ix_answers_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_answers_id ON public.answers USING btree (id);


--
-- Name: ix_answers_question_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_answers_question_id ON public.answers USING btree (question_id);


--
-- Name: ix_categories_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_categories_id ON public.categories USING btree (id);


--
-- Name: ix_comments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_comments_id ON public.comments USING btree (id);


--
-- Name: ix_comments_lesson_parent_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_comments_lesson_parent_created_at ON public.comments USING btree (lesson_id, parent_comment_id, created_at);


--
-- Name: ix_comments_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_comments_user_id ON public.comments USING btree (user_id);


--
-- Name: ix_contact_messages_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contact_messages_id ON public.contact_messages USING btree (id);


--
-- Name: ix_courses_category_id_rating; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_category_id_rating ON public.courses USING btree (category_id, rating);


--
-- Name: ix_courses_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_id ON public.courses USING btree (id);


--
-- Name: ix_courses_rating; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_rating ON public.courses USING btree (rating);


--
-- Name: ix_courses_teacher_id_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_teacher_id_created_at ON public.courses USING btree (teacher_id, created_at);


--
-- Name: ix_group_homework_notifications_student_read; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_homework_notifications_student_read ON public.group_homework_notifications USING btree (student_id, read_at);


--
-- Name: ix_group_homework_submissions_homework_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_homework_submissions_homework_id ON public.group_homework_submissions USING btree (homework_id);


--
-- Name: ix_group_homework_submissions_reviewed_by_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_homework_submissions_reviewed_by_id ON public.group_homework_submissions USING btree (reviewed_by_id);


--
-- Name: ix_group_homework_submissions_student_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_homework_submissions_student_id ON public.group_homework_submissions USING btree (student_id);


--
-- Name: ix_group_homeworks_created_by_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_homeworks_created_by_id ON public.group_homeworks USING btree (created_by_id);


--
-- Name: ix_group_homeworks_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_homeworks_group_id ON public.group_homeworks USING btree (group_id);


--
-- Name: ix_group_homeworks_lesson_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_homeworks_lesson_id ON public.group_homeworks USING btree (lesson_id);


--
-- Name: ix_group_journal_entries_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_journal_entries_group_id ON public.group_journal_entries USING btree (group_id);


--
-- Name: ix_group_journal_entries_lesson_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_journal_entries_lesson_id ON public.group_journal_entries USING btree (lesson_id);


--
-- Name: ix_group_journal_entries_student_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_journal_entries_student_id ON public.group_journal_entries USING btree (student_id);


--
-- Name: ix_group_lesson_chat_group_lesson; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_lesson_chat_group_lesson ON public.group_lesson_chat_messages USING btree (group_id, lesson_id);


--
-- Name: ix_group_lesson_chat_lesson_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_lesson_chat_lesson_created ON public.group_lesson_chat_messages USING btree (lesson_id, created_at);


--
-- Name: ix_group_lesson_chat_messages_recipient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_lesson_chat_messages_recipient_id ON public.group_lesson_chat_messages USING btree (recipient_id);


--
-- Name: ix_group_lesson_chat_messages_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_lesson_chat_messages_user_id ON public.group_lesson_chat_messages USING btree (user_id);


--
-- Name: ix_group_lesson_chat_scope_lesson; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_lesson_chat_scope_lesson ON public.group_lesson_chat_messages USING btree (lesson_id, message_scope, created_at);


--
-- Name: ix_group_lesson_progress_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_lesson_progress_group_id ON public.group_lesson_progress USING btree (group_id);


--
-- Name: ix_group_lesson_progress_lesson_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_lesson_progress_lesson_id ON public.group_lesson_progress USING btree (lesson_id);


--
-- Name: ix_group_lesson_progress_student_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_lesson_progress_student_id ON public.group_lesson_progress USING btree (student_id);


--
-- Name: ix_group_lesson_sessions_group_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_lesson_sessions_group_status ON public.group_lesson_sessions USING btree (group_id, status);


--
-- Name: ix_group_lessons_group_id_order; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_lessons_group_id_order ON public.group_lessons USING btree (group_id, "order");


--
-- Name: ix_group_lessons_group_module_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_lessons_group_module_id ON public.group_lessons USING btree (group_module_id);


--
-- Name: ix_group_materials_lesson_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_materials_lesson_id ON public.group_materials USING btree (lesson_id);


--
-- Name: ix_group_members_student_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_members_student_id ON public.group_members USING btree (student_id);


--
-- Name: ix_group_modules_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_modules_group_id ON public.group_modules USING btree (group_id);


--
-- Name: ix_group_modules_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_modules_id ON public.group_modules USING btree (id);


--
-- Name: ix_group_payment_entries_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_payment_entries_group_id ON public.group_payment_entries USING btree (group_id);


--
-- Name: ix_group_payment_entries_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_payment_entries_month ON public.group_payment_entries USING btree (month);


--
-- Name: ix_group_payment_entries_student_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_payment_entries_student_id ON public.group_payment_entries USING btree (student_id);


--
-- Name: ix_groups_org_id_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_groups_org_id_created_at ON public.groups USING btree (organization_id, created_at);


--
-- Name: ix_groups_teacher_id_active_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_groups_teacher_id_active_created_at ON public.groups USING btree (teacher_id, is_active, created_at);


--
-- Name: ix_lessons_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lessons_id ON public.lessons USING btree (id);


--
-- Name: ix_lessons_module_id_order_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lessons_module_id_order_index ON public.lessons USING btree (module_id, order_index);


--
-- Name: ix_materials_course_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_materials_course_id ON public.materials USING btree (course_id);


--
-- Name: ix_materials_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_materials_id ON public.materials USING btree (id);


--
-- Name: ix_modules_course_id_order_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_modules_course_id_order_index ON public.modules USING btree (course_id, order_index);


--
-- Name: ix_modules_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_modules_id ON public.modules USING btree (id);


--
-- Name: ix_org_announcement_dismissals_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_org_announcement_dismissals_user ON public.organization_announcement_dismissals USING btree (user_id);


--
-- Name: ix_org_announcements_audience_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_org_announcements_audience_expires ON public.organization_announcements USING btree (audience, expires_at);


--
-- Name: ix_org_announcements_org_active_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_org_announcements_org_active_created ON public.organization_announcements USING btree (organization_id, is_active, created_at);


--
-- Name: ix_org_students_org_id_status_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_org_students_org_id_status_created_at ON public.organization_students USING btree (organization_id, status, created_at);


--
-- Name: ix_org_students_student_id_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_org_students_student_id_status ON public.organization_students USING btree (student_id, status);


--
-- Name: ix_org_teachers_org_id_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_org_teachers_org_id_status ON public.organization_teachers USING btree (organization_id, status);


--
-- Name: ix_org_teachers_teacher_id_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_org_teachers_teacher_id_status ON public.organization_teachers USING btree (teacher_id, status);


--
-- Name: ix_organizations_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_organizations_created_at ON public.organizations USING btree (created_at);


--
-- Name: ix_organizations_status_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_organizations_status_name ON public.organizations USING btree (status, name);


--
-- Name: ix_password_reset_tokens_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_password_reset_tokens_expires_at ON public.password_reset_tokens USING btree (expires_at);


--
-- Name: ix_password_reset_tokens_token_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_password_reset_tokens_token_hash ON public.password_reset_tokens USING btree (token_hash);


--
-- Name: ix_password_reset_tokens_used_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_password_reset_tokens_used_at ON public.password_reset_tokens USING btree (used_at);


--
-- Name: ix_password_reset_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_password_reset_tokens_user_id ON public.password_reset_tokens USING btree (user_id);


--
-- Name: ix_progress_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_progress_id ON public.progress USING btree (id);


--
-- Name: ix_progress_student_completed_completed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_progress_student_completed_completed_at ON public.progress USING btree (student_id, completed, completed_at);


--
-- Name: ix_push_subscriptions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_push_subscriptions_id ON public.push_subscriptions USING btree (id);


--
-- Name: ix_push_subscriptions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_push_subscriptions_user_id ON public.push_subscriptions USING btree (user_id);


--
-- Name: ix_questions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_questions_id ON public.questions USING btree (id);


--
-- Name: ix_questions_quiz_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_questions_quiz_id ON public.questions USING btree (quiz_id);


--
-- Name: ix_quiz_attempts_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quiz_attempts_id ON public.quiz_attempts USING btree (id);


--
-- Name: ix_quiz_attempts_student_id_quiz_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quiz_attempts_student_id_quiz_id ON public.quiz_attempts USING btree (student_id, quiz_id);


--
-- Name: ix_quiz_results_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quiz_results_id ON public.quiz_results USING btree (id);


--
-- Name: ix_quizzes_course_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quizzes_course_id ON public.quizzes USING btree (course_id);


--
-- Name: ix_quizzes_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quizzes_id ON public.quizzes USING btree (id);


--
-- Name: ix_quizzes_lesson_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quizzes_lesson_id ON public.quizzes USING btree (lesson_id);


--
-- Name: ix_quizzes_module_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quizzes_module_id ON public.quizzes USING btree (module_id);


--
-- Name: ix_reviews_course_rating_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reviews_course_rating_created_at ON public.reviews USING btree (course_id, rating, created_at);


--
-- Name: ix_reviews_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reviews_id ON public.reviews USING btree (id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_vocabulary_attempt_answers_attempt_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vocabulary_attempt_answers_attempt_id ON public.vocabulary_attempt_answers USING btree (attempt_id);


--
-- Name: ix_vocabulary_attempt_answers_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vocabulary_attempt_answers_id ON public.vocabulary_attempt_answers USING btree (id);


--
-- Name: ix_vocabulary_attempts_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vocabulary_attempts_id ON public.vocabulary_attempts USING btree (id);


--
-- Name: ix_vocabulary_attempts_student_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vocabulary_attempts_student_id ON public.vocabulary_attempts USING btree (student_id);


--
-- Name: ix_vocabulary_attempts_vocab_set_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vocabulary_attempts_vocab_set_id ON public.vocabulary_attempts USING btree (vocab_set_id);


--
-- Name: ix_vocabulary_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vocabulary_items_id ON public.vocabulary_items USING btree (id);


--
-- Name: ix_vocabulary_items_vocab_set_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vocabulary_items_vocab_set_id ON public.vocabulary_items USING btree (vocab_set_id);


--
-- Name: ix_vocabulary_sets_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vocabulary_sets_id ON public.vocabulary_sets USING btree (id);


--
-- Name: ix_vocabulary_sets_lesson_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vocabulary_sets_lesson_id ON public.vocabulary_sets USING btree (lesson_id);


--
-- Name: ux_courses_single_guest_accessible; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_courses_single_guest_accessible ON public.courses USING btree (is_guest_accessible) WHERE (is_guest_accessible = true);


--
-- Name: answers answers_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.answers
    ADD CONSTRAINT answers_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.questions(id) ON DELETE CASCADE;


--
-- Name: comments comments_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE CASCADE;


--
-- Name: comments comments_parent_comment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_parent_comment_id_fkey FOREIGN KEY (parent_comment_id) REFERENCES public.comments(id) ON DELETE CASCADE;


--
-- Name: comments comments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: courses courses_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.courses
    ADD CONSTRAINT courses_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: courses courses_teacher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.courses
    ADD CONSTRAINT courses_teacher_id_fkey FOREIGN KEY (teacher_id) REFERENCES public.users(id);


--
-- Name: group_homework_submissions fk_group_homework_submissions_reviewed_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homework_submissions
    ADD CONSTRAINT fk_group_homework_submissions_reviewed_by FOREIGN KEY (reviewed_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: group_lesson_chat_messages fk_group_lesson_chat_messages_recipient_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_chat_messages
    ADD CONSTRAINT fk_group_lesson_chat_messages_recipient_id_users FOREIGN KEY (recipient_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: group_lessons fk_group_lessons_group_module_id_group_modules; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lessons
    ADD CONSTRAINT fk_group_lessons_group_module_id_group_modules FOREIGN KEY (group_module_id) REFERENCES public.group_modules(id) ON DELETE SET NULL;


--
-- Name: group_homework_notifications group_homework_notifications_homework_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homework_notifications
    ADD CONSTRAINT group_homework_notifications_homework_id_fkey FOREIGN KEY (homework_id) REFERENCES public.group_homeworks(id) ON DELETE CASCADE;


--
-- Name: group_homework_notifications group_homework_notifications_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homework_notifications
    ADD CONSTRAINT group_homework_notifications_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: group_homework_submissions group_homework_submissions_homework_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homework_submissions
    ADD CONSTRAINT group_homework_submissions_homework_id_fkey FOREIGN KEY (homework_id) REFERENCES public.group_homeworks(id) ON DELETE CASCADE;


--
-- Name: group_homework_submissions group_homework_submissions_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homework_submissions
    ADD CONSTRAINT group_homework_submissions_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: group_homeworks group_homeworks_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homeworks
    ADD CONSTRAINT group_homeworks_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: group_homeworks group_homeworks_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homeworks
    ADD CONSTRAINT group_homeworks_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE;


--
-- Name: group_homeworks group_homeworks_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_homeworks
    ADD CONSTRAINT group_homeworks_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.group_lessons(id) ON DELETE CASCADE;


--
-- Name: group_journal_entries group_journal_entries_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_journal_entries
    ADD CONSTRAINT group_journal_entries_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE;


--
-- Name: group_journal_entries group_journal_entries_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_journal_entries
    ADD CONSTRAINT group_journal_entries_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.group_lessons(id) ON DELETE CASCADE;


--
-- Name: group_journal_entries group_journal_entries_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_journal_entries
    ADD CONSTRAINT group_journal_entries_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: group_lesson_chat_messages group_lesson_chat_messages_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_chat_messages
    ADD CONSTRAINT group_lesson_chat_messages_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE;


--
-- Name: group_lesson_chat_messages group_lesson_chat_messages_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_chat_messages
    ADD CONSTRAINT group_lesson_chat_messages_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.group_lessons(id) ON DELETE CASCADE;


--
-- Name: group_lesson_chat_messages group_lesson_chat_messages_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_chat_messages
    ADD CONSTRAINT group_lesson_chat_messages_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: group_lesson_progress group_lesson_progress_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_progress
    ADD CONSTRAINT group_lesson_progress_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE;


--
-- Name: group_lesson_progress group_lesson_progress_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_progress
    ADD CONSTRAINT group_lesson_progress_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.group_lessons(id) ON DELETE CASCADE;


--
-- Name: group_lesson_progress group_lesson_progress_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_progress
    ADD CONSTRAINT group_lesson_progress_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: group_lesson_sessions group_lesson_sessions_completed_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_sessions
    ADD CONSTRAINT group_lesson_sessions_completed_by_id_fkey FOREIGN KEY (completed_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: group_lesson_sessions group_lesson_sessions_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_sessions
    ADD CONSTRAINT group_lesson_sessions_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE;


--
-- Name: group_lesson_sessions group_lesson_sessions_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_sessions
    ADD CONSTRAINT group_lesson_sessions_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.group_lessons(id) ON DELETE CASCADE;


--
-- Name: group_lesson_sessions group_lesson_sessions_started_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lesson_sessions
    ADD CONSTRAINT group_lesson_sessions_started_by_id_fkey FOREIGN KEY (started_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: group_lessons group_lessons_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_lessons
    ADD CONSTRAINT group_lessons_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: group_materials group_materials_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_materials
    ADD CONSTRAINT group_materials_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.group_lessons(id);


--
-- Name: group_members group_members_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_members
    ADD CONSTRAINT group_members_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: group_members group_members_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_members
    ADD CONSTRAINT group_members_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id);


--
-- Name: group_modules group_modules_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_modules
    ADD CONSTRAINT group_modules_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE;


--
-- Name: group_payment_entries group_payment_entries_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_payment_entries
    ADD CONSTRAINT group_payment_entries_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE;


--
-- Name: group_payment_entries group_payment_entries_marked_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_payment_entries
    ADD CONSTRAINT group_payment_entries_marked_by_id_fkey FOREIGN KEY (marked_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: group_payment_entries group_payment_entries_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_payment_entries
    ADD CONSTRAINT group_payment_entries_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: groups groups_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: groups groups_teacher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_teacher_id_fkey FOREIGN KEY (teacher_id) REFERENCES public.users(id);


--
-- Name: lessons lessons_module_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lessons
    ADD CONSTRAINT lessons_module_id_fkey FOREIGN KEY (module_id) REFERENCES public.modules(id) ON DELETE CASCADE;


--
-- Name: materials materials_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.materials
    ADD CONSTRAINT materials_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: materials materials_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.materials
    ADD CONSTRAINT materials_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE CASCADE;


--
-- Name: modules modules_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.modules
    ADD CONSTRAINT modules_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: organization_announcement_dismissals organization_announcement_dismissals_announcement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_announcement_dismissals
    ADD CONSTRAINT organization_announcement_dismissals_announcement_id_fkey FOREIGN KEY (announcement_id) REFERENCES public.organization_announcements(id) ON DELETE CASCADE;


--
-- Name: organization_announcement_dismissals organization_announcement_dismissals_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_announcement_dismissals
    ADD CONSTRAINT organization_announcement_dismissals_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: organization_announcements organization_announcements_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_announcements
    ADD CONSTRAINT organization_announcements_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: organization_announcements organization_announcements_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_announcements
    ADD CONSTRAINT organization_announcements_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: organization_students organization_students_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_students
    ADD CONSTRAINT organization_students_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: organization_students organization_students_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_students
    ADD CONSTRAINT organization_students_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id);


--
-- Name: organization_teachers organization_teachers_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_teachers
    ADD CONSTRAINT organization_teachers_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: organization_teachers organization_teachers_teacher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_teachers
    ADD CONSTRAINT organization_teachers_teacher_id_fkey FOREIGN KEY (teacher_id) REFERENCES public.users(id);


--
-- Name: organizations organizations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: progress progress_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.progress
    ADD CONSTRAINT progress_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE CASCADE;


--
-- Name: progress progress_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.progress
    ADD CONSTRAINT progress_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: push_subscriptions push_subscriptions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: questions questions_quiz_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.questions
    ADD CONSTRAINT questions_quiz_id_fkey FOREIGN KEY (quiz_id) REFERENCES public.quizzes(id) ON DELETE CASCADE;


--
-- Name: quiz_attempts quiz_attempts_quiz_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts
    ADD CONSTRAINT quiz_attempts_quiz_id_fkey FOREIGN KEY (quiz_id) REFERENCES public.quizzes(id) ON DELETE CASCADE;


--
-- Name: quiz_attempts quiz_attempts_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts
    ADD CONSTRAINT quiz_attempts_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: quiz_results quiz_results_quiz_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_results
    ADD CONSTRAINT quiz_results_quiz_id_fkey FOREIGN KEY (quiz_id) REFERENCES public.quizzes(id) ON DELETE CASCADE;


--
-- Name: quiz_results quiz_results_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_results
    ADD CONSTRAINT quiz_results_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: quizzes quizzes_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes
    ADD CONSTRAINT quizzes_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: quizzes quizzes_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes
    ADD CONSTRAINT quizzes_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE CASCADE;


--
-- Name: quizzes quizzes_module_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes
    ADD CONSTRAINT quizzes_module_id_fkey FOREIGN KEY (module_id) REFERENCES public.modules(id) ON DELETE CASCADE;


--
-- Name: reviews reviews_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: reviews reviews_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: reviews reviews_teacher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_teacher_id_fkey FOREIGN KEY (teacher_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: vocabulary_attempt_answers vocabulary_attempt_answers_attempt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_attempt_answers
    ADD CONSTRAINT vocabulary_attempt_answers_attempt_id_fkey FOREIGN KEY (attempt_id) REFERENCES public.vocabulary_attempts(id) ON DELETE CASCADE;


--
-- Name: vocabulary_attempt_answers vocabulary_attempt_answers_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_attempt_answers
    ADD CONSTRAINT vocabulary_attempt_answers_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.vocabulary_items(id) ON DELETE CASCADE;


--
-- Name: vocabulary_attempts vocabulary_attempts_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_attempts
    ADD CONSTRAINT vocabulary_attempts_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: vocabulary_attempts vocabulary_attempts_vocab_set_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_attempts
    ADD CONSTRAINT vocabulary_attempts_vocab_set_id_fkey FOREIGN KEY (vocab_set_id) REFERENCES public.vocabulary_sets(id) ON DELETE CASCADE;


--
-- Name: vocabulary_items vocabulary_items_vocab_set_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_items
    ADD CONSTRAINT vocabulary_items_vocab_set_id_fkey FOREIGN KEY (vocab_set_id) REFERENCES public.vocabulary_sets(id) ON DELETE CASCADE;


--
-- Name: vocabulary_sets vocabulary_sets_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_sets
    ADD CONSTRAINT vocabulary_sets_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.group_lessons(id) ON DELETE CASCADE;


--
-- Name: answers; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.answers ENABLE ROW LEVEL SECURITY;

--
-- Name: categories; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;

--
-- Name: comments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.comments ENABLE ROW LEVEL SECURITY;

--
-- Name: contact_messages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.contact_messages ENABLE ROW LEVEL SECURITY;

--
-- Name: group_homework_notifications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.group_homework_notifications ENABLE ROW LEVEL SECURITY;

--
-- Name: group_homework_submissions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.group_homework_submissions ENABLE ROW LEVEL SECURITY;

--
-- Name: group_homeworks; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.group_homeworks ENABLE ROW LEVEL SECURITY;

--
-- Name: group_journal_entries; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.group_journal_entries ENABLE ROW LEVEL SECURITY;

--
-- Name: group_lesson_chat_messages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.group_lesson_chat_messages ENABLE ROW LEVEL SECURITY;

--
-- Name: group_lesson_progress; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.group_lesson_progress ENABLE ROW LEVEL SECURITY;

--
-- Name: group_lesson_sessions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.group_lesson_sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: group_lessons; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.group_lessons ENABLE ROW LEVEL SECURITY;

--
-- Name: group_materials; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.group_materials ENABLE ROW LEVEL SECURITY;

--
-- Name: group_members; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.group_members ENABLE ROW LEVEL SECURITY;

--
-- Name: group_modules; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.group_modules ENABLE ROW LEVEL SECURITY;

--
-- Name: group_payment_entries; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.group_payment_entries ENABLE ROW LEVEL SECURITY;

--
-- Name: groups; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.groups ENABLE ROW LEVEL SECURITY;

--
-- Name: organization_announcement_dismissals; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organization_announcement_dismissals ENABLE ROW LEVEL SECURITY;

--
-- Name: organization_announcements; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organization_announcements ENABLE ROW LEVEL SECURITY;

--
-- Name: organization_students; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organization_students ENABLE ROW LEVEL SECURITY;

--
-- Name: organization_teachers; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organization_teachers ENABLE ROW LEVEL SECURITY;

--
-- Name: organizations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;

--
-- Name: password_reset_tokens; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.password_reset_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: push_subscriptions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.push_subscriptions ENABLE ROW LEVEL SECURITY;

--
-- Name: quiz_attempts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.quiz_attempts ENABLE ROW LEVEL SECURITY;

--
-- Name: vocabulary_attempt_answers; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vocabulary_attempt_answers ENABLE ROW LEVEL SECURITY;

--
-- Name: vocabulary_attempts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vocabulary_attempts ENABLE ROW LEVEL SECURITY;

--
-- Name: vocabulary_items; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vocabulary_items ENABLE ROW LEVEL SECURITY;

--
-- Name: vocabulary_sets; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vocabulary_sets ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(BASELINE_SQL)


def downgrade() -> None:
    raise NotImplementedError("Downgrade of the Furuzon baseline is intentionally unsupported.")
