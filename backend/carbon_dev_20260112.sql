--
-- PostgreSQL database dump
--

\restrict XE8gsjNMsyIncbiIOjk3Ea1vDDEAHzF9jNY9NJbvMM4jRLzzZ6VymTjBWNTbSLc

-- Dumped from database version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public.token_blacklist_outstandingtoken DROP CONSTRAINT IF EXISTS token_blacklist_outs_user_id_83bc629a_fk_accounts_;
ALTER TABLE IF EXISTS ONLY public.token_blacklist_blacklistedtoken DROP CONSTRAINT IF EXISTS token_blacklist_blacklistedtoken_token_id_3cc7fe56_fk;
ALTER TABLE IF EXISTS ONLY public.django_admin_log DROP CONSTRAINT IF EXISTS django_admin_log_user_id_c564eba6_fk_accounts_user_id;
ALTER TABLE IF EXISTS ONLY public.django_admin_log DROP CONSTRAINT IF EXISTS django_admin_log_content_type_id_c4bce8eb_fk_django_co;
ALTER TABLE IF EXISTS ONLY public.dataschema_schemachangelog DROP CONSTRAINT IF EXISTS dataschema_schemachangelog_user_id_010cccc3_fk_accounts_user_id;
ALTER TABLE IF EXISTS ONLY public.dataschema_schemachangelog DROP CONSTRAINT IF EXISTS dataschema_schemacha_data_table_id_d5e079de_fk_dataschem;
ALTER TABLE IF EXISTS ONLY public.dataschema_schemachangelog DROP CONSTRAINT IF EXISTS dataschema_schemacha_data_field_id_34bef2f5_fk_dataschem;
ALTER TABLE IF EXISTS ONLY public.dataschema_datatable DROP CONSTRAINT IF EXISTS dataschema_datatable_updated_by_id_9f76f540_fk_accounts_user_id;
ALTER TABLE IF EXISTS ONLY public.dataschema_datatable DROP CONSTRAINT IF EXISTS dataschema_datatable_module_id_c6e4e57a_fk_core_module_id;
ALTER TABLE IF EXISTS ONLY public.dataschema_datatable DROP CONSTRAINT IF EXISTS dataschema_datatable_created_by_id_48dbe5dd_fk_accounts_user_id;
ALTER TABLE IF EXISTS ONLY public.dataschema_datarow DROP CONSTRAINT IF EXISTS dataschema_datarow_updated_by_id_1a3ab18c_fk_accounts_user_id;
ALTER TABLE IF EXISTS ONLY public.dataschema_datarow DROP CONSTRAINT IF EXISTS dataschema_datarow_data_table_id_7b1671a8_fk_dataschem;
ALTER TABLE IF EXISTS ONLY public.dataschema_datarow DROP CONSTRAINT IF EXISTS dataschema_datarow_created_by_id_e77d0dd9_fk_accounts_user_id;
ALTER TABLE IF EXISTS ONLY public.dataschema_datafield DROP CONSTRAINT IF EXISTS dataschema_datafield_updated_by_id_81c3db8e_fk_accounts_user_id;
ALTER TABLE IF EXISTS ONLY public.dataschema_datafield DROP CONSTRAINT IF EXISTS dataschema_datafield_reference_table_id_e1ddcd6d_fk_dataschem;
ALTER TABLE IF EXISTS ONLY public.dataschema_datafield DROP CONSTRAINT IF EXISTS dataschema_datafield_data_table_id_8c790d12_fk_dataschem;
ALTER TABLE IF EXISTS ONLY public.dataschema_datafield DROP CONSTRAINT IF EXISTS dataschema_datafield_created_by_id_ae56955f_fk_accounts_user_id;
ALTER TABLE IF EXISTS ONLY public.core_project DROP CONSTRAINT IF EXISTS core_project_tenant_id_560cac1a_fk_accounts_tenant_id;
ALTER TABLE IF EXISTS ONLY public.core_module DROP CONSTRAINT IF EXISTS core_module_project_id_63dc3a7f_fk_core_project_id;
ALTER TABLE IF EXISTS ONLY public.auth_permission DROP CONSTRAINT IF EXISTS auth_permission_content_type_id_2f476e4b_fk_django_co;
ALTER TABLE IF EXISTS ONLY public.auth_group_permissions DROP CONSTRAINT IF EXISTS auth_group_permissions_group_id_b120cbf9_fk_auth_group_id;
ALTER TABLE IF EXISTS ONLY public.auth_group_permissions DROP CONSTRAINT IF EXISTS auth_group_permissio_permission_id_84c5c92e_fk_auth_perm;
ALTER TABLE IF EXISTS ONLY public.ai_copilot_useraipreference DROP CONSTRAINT IF EXISTS ai_copilot_useraipre_user_id_9deba3cb_fk_accounts_;
ALTER TABLE IF EXISTS ONLY public.ai_copilot_proactiveinsight DROP CONSTRAINT IF EXISTS ai_copilot_proactive_user_id_fbf921b1_fk_accounts_;
ALTER TABLE IF EXISTS ONLY public.ai_copilot_proactiveinsight DROP CONSTRAINT IF EXISTS ai_copilot_proactive_project_id_e67c32a7_fk_core_proj;
ALTER TABLE IF EXISTS ONLY public.ai_copilot_conversationmessage DROP CONSTRAINT IF EXISTS ai_copilot_conversat_user_id_e9c0469d_fk_accounts_;
ALTER TABLE IF EXISTS ONLY public.ai_copilot_conversationmessage DROP CONSTRAINT IF EXISTS ai_copilot_conversat_project_id_34619dd3_fk_core_proj;
ALTER TABLE IF EXISTS ONLY public.accounts_user_user_permissions DROP CONSTRAINT IF EXISTS accounts_user_user_p_user_id_e4f0a161_fk_accounts_;
ALTER TABLE IF EXISTS ONLY public.accounts_user_user_permissions DROP CONSTRAINT IF EXISTS accounts_user_user_p_permission_id_113bb443_fk_auth_perm;
ALTER TABLE IF EXISTS ONLY public.accounts_user DROP CONSTRAINT IF EXISTS accounts_user_tenant_id_1906c0a8_fk_accounts_tenant_id;
ALTER TABLE IF EXISTS ONLY public.accounts_user_groups DROP CONSTRAINT IF EXISTS accounts_user_groups_user_id_52b62117_fk_accounts_user_id;
ALTER TABLE IF EXISTS ONLY public.accounts_user_groups DROP CONSTRAINT IF EXISTS accounts_user_groups_group_id_bd11a704_fk_auth_group_id;
ALTER TABLE IF EXISTS ONLY public.accounts_scopedrole DROP CONSTRAINT IF EXISTS accounts_scopedrole_user_id_739af120_fk_accounts_user_id;
ALTER TABLE IF EXISTS ONLY public.accounts_scopedrole DROP CONSTRAINT IF EXISTS accounts_scopedrole_tenant_id_1c7f2393_fk_accounts_tenant_id;
ALTER TABLE IF EXISTS ONLY public.accounts_scopedrole DROP CONSTRAINT IF EXISTS accounts_scopedrole_project_id_c1692ed0_fk_core_project_id;
ALTER TABLE IF EXISTS ONLY public.accounts_scopedrole DROP CONSTRAINT IF EXISTS accounts_scopedrole_module_id_8b78908b_fk_core_module_id;
ALTER TABLE IF EXISTS ONLY public.accounts_scopedrole DROP CONSTRAINT IF EXISTS accounts_scopedrole_group_id_cf584c29_fk_auth_group_id;
ALTER TABLE IF EXISTS ONLY public.accounts_roleassignmentauditlog DROP CONSTRAINT IF EXISTS accounts_roleassignm_user_id_e2fac962_fk_accounts_;
ALTER TABLE IF EXISTS ONLY public.accounts_roleassignmentauditlog DROP CONSTRAINT IF EXISTS accounts_roleassignm_tenant_id_54dff115_fk_accounts_;
ALTER TABLE IF EXISTS ONLY public.accounts_roleassignmentauditlog DROP CONSTRAINT IF EXISTS accounts_roleassignm_project_id_cb535b5f_fk_core_proj;
ALTER TABLE IF EXISTS ONLY public.accounts_roleassignmentauditlog DROP CONSTRAINT IF EXISTS accounts_roleassignm_module_id_584e05ea_fk_core_modu;
ALTER TABLE IF EXISTS ONLY public.accounts_roleassignmentauditlog DROP CONSTRAINT IF EXISTS accounts_roleassignm_group_id_0f6b152e_fk_auth_grou;
ALTER TABLE IF EXISTS ONLY public.accounts_roleassignmentauditlog DROP CONSTRAINT IF EXISTS accounts_roleassignm_actor_id_8dc20397_fk_accounts_;
DROP INDEX IF EXISTS public.token_blacklist_outstandingtoken_user_id_83bc629a;
DROP INDEX IF EXISTS public.token_blacklist_outstandingtoken_jti_hex_d9bdf6f7_like;
DROP INDEX IF EXISTS public.django_session_session_key_c0390e0f_like;
DROP INDEX IF EXISTS public.django_session_expire_date_a5c62663;
DROP INDEX IF EXISTS public.django_admin_log_user_id_c564eba6;
DROP INDEX IF EXISTS public.django_admin_log_content_type_id_c4bce8eb;
DROP INDEX IF EXISTS public.dataschema_schemachangelog_user_id_010cccc3;
DROP INDEX IF EXISTS public.dataschema_schemachangelog_data_table_id_d5e079de;
DROP INDEX IF EXISTS public.dataschema_schemachangelog_data_field_id_34bef2f5;
DROP INDEX IF EXISTS public.dataschema_datatable_updated_by_id_9f76f540;
DROP INDEX IF EXISTS public.dataschema_datatable_name_13303929_like;
DROP INDEX IF EXISTS public.dataschema_datatable_name_13303929;
DROP INDEX IF EXISTS public.dataschema_datatable_module_id_c6e4e57a;
DROP INDEX IF EXISTS public.dataschema_datatable_created_by_id_48dbe5dd;
DROP INDEX IF EXISTS public.dataschema_datarow_updated_by_id_1a3ab18c;
DROP INDEX IF EXISTS public.dataschema_datarow_data_table_id_7b1671a8;
DROP INDEX IF EXISTS public.dataschema_datarow_created_by_id_e77d0dd9;
DROP INDEX IF EXISTS public.dataschema_datafield_updated_by_id_81c3db8e;
DROP INDEX IF EXISTS public.dataschema_datafield_reference_table_id_e1ddcd6d;
DROP INDEX IF EXISTS public.dataschema_datafield_data_table_id_8c790d12;
DROP INDEX IF EXISTS public.dataschema_datafield_created_by_id_ae56955f;
DROP INDEX IF EXISTS public.core_project_tenant_id_560cac1a;
DROP INDEX IF EXISTS public.core_module_project_id_63dc3a7f;
DROP INDEX IF EXISTS public.auth_permission_content_type_id_2f476e4b;
DROP INDEX IF EXISTS public.auth_group_permissions_permission_id_84c5c92e;
DROP INDEX IF EXISTS public.auth_group_permissions_group_id_b120cbf9;
DROP INDEX IF EXISTS public.auth_group_name_a6ea08ec_like;
DROP INDEX IF EXISTS public.ai_copilot_proactiveinsight_user_id_fbf921b1;
DROP INDEX IF EXISTS public.ai_copilot_proactiveinsight_project_id_e67c32a7;
DROP INDEX IF EXISTS public.ai_copilot_conversationmessage_user_id_e9c0469d;
DROP INDEX IF EXISTS public.ai_copilot_conversationmessage_project_id_34619dd3;
DROP INDEX IF EXISTS public.ai_copilot__user_id_7ac4e4_idx;
DROP INDEX IF EXISTS public.ai_copilot__user_id_2ff702_idx;
DROP INDEX IF EXISTS public.ai_copilot__project_27b666_idx;
DROP INDEX IF EXISTS public.ai_copilot__project_243753_idx;
DROP INDEX IF EXISTS public.accounts_user_username_6088629e_like;
DROP INDEX IF EXISTS public.accounts_user_user_permissions_user_id_e4f0a161;
DROP INDEX IF EXISTS public.accounts_user_user_permissions_permission_id_113bb443;
DROP INDEX IF EXISTS public.accounts_user_tenant_id_1906c0a8;
DROP INDEX IF EXISTS public.accounts_user_groups_user_id_52b62117;
DROP INDEX IF EXISTS public.accounts_user_groups_group_id_bd11a704;
DROP INDEX IF EXISTS public.accounts_tenant_name_62906664_like;
DROP INDEX IF EXISTS public.accounts_scopedrole_user_id_739af120;
DROP INDEX IF EXISTS public.accounts_scopedrole_tenant_id_1c7f2393;
DROP INDEX IF EXISTS public.accounts_scopedrole_project_id_c1692ed0;
DROP INDEX IF EXISTS public.accounts_scopedrole_module_id_8b78908b;
DROP INDEX IF EXISTS public.accounts_scopedrole_group_id_cf584c29;
DROP INDEX IF EXISTS public.accounts_roleassignmentauditlog_user_id_e2fac962;
DROP INDEX IF EXISTS public.accounts_roleassignmentauditlog_tenant_id_54dff115;
DROP INDEX IF EXISTS public.accounts_roleassignmentauditlog_project_id_cb535b5f;
DROP INDEX IF EXISTS public.accounts_roleassignmentauditlog_module_id_584e05ea;
DROP INDEX IF EXISTS public.accounts_roleassignmentauditlog_group_id_0f6b152e;
DROP INDEX IF EXISTS public.accounts_roleassignmentauditlog_actor_id_8dc20397;
ALTER TABLE IF EXISTS ONLY public.token_blacklist_outstandingtoken DROP CONSTRAINT IF EXISTS token_blacklist_outstandingtoken_pkey;
ALTER TABLE IF EXISTS ONLY public.token_blacklist_outstandingtoken DROP CONSTRAINT IF EXISTS token_blacklist_outstandingtoken_jti_hex_d9bdf6f7_uniq;
ALTER TABLE IF EXISTS ONLY public.token_blacklist_blacklistedtoken DROP CONSTRAINT IF EXISTS token_blacklist_blacklistedtoken_token_id_key;
ALTER TABLE IF EXISTS ONLY public.token_blacklist_blacklistedtoken DROP CONSTRAINT IF EXISTS token_blacklist_blacklistedtoken_pkey;
ALTER TABLE IF EXISTS ONLY public.django_session DROP CONSTRAINT IF EXISTS django_session_pkey;
ALTER TABLE IF EXISTS ONLY public.django_migrations DROP CONSTRAINT IF EXISTS django_migrations_pkey;
ALTER TABLE IF EXISTS ONLY public.django_content_type DROP CONSTRAINT IF EXISTS django_content_type_pkey;
ALTER TABLE IF EXISTS ONLY public.django_content_type DROP CONSTRAINT IF EXISTS django_content_type_app_label_model_76bd3d3b_uniq;
ALTER TABLE IF EXISTS ONLY public.django_admin_log DROP CONSTRAINT IF EXISTS django_admin_log_pkey;
ALTER TABLE IF EXISTS ONLY public.dataschema_schemachangelog DROP CONSTRAINT IF EXISTS dataschema_schemachangelog_pkey;
ALTER TABLE IF EXISTS ONLY public.dataschema_datatable DROP CONSTRAINT IF EXISTS dataschema_datatable_pkey;
ALTER TABLE IF EXISTS ONLY public.dataschema_datatable DROP CONSTRAINT IF EXISTS dataschema_datatable_module_id_name_0414ec63_uniq;
ALTER TABLE IF EXISTS ONLY public.dataschema_datarow DROP CONSTRAINT IF EXISTS dataschema_datarow_pkey;
ALTER TABLE IF EXISTS ONLY public.dataschema_datafield DROP CONSTRAINT IF EXISTS dataschema_datafield_pkey;
ALTER TABLE IF EXISTS ONLY public.dataschema_datafield DROP CONSTRAINT IF EXISTS dataschema_datafield_data_table_id_name_5996a3bc_uniq;
ALTER TABLE IF EXISTS ONLY public.core_project DROP CONSTRAINT IF EXISTS core_project_tenant_id_name_566c090f_uniq;
ALTER TABLE IF EXISTS ONLY public.core_project DROP CONSTRAINT IF EXISTS core_project_pkey;
ALTER TABLE IF EXISTS ONLY public.core_module DROP CONSTRAINT IF EXISTS core_module_project_id_name_66ce4d0c_uniq;
ALTER TABLE IF EXISTS ONLY public.core_module DROP CONSTRAINT IF EXISTS core_module_pkey;
ALTER TABLE IF EXISTS ONLY public.core_feedback DROP CONSTRAINT IF EXISTS core_feedback_pkey;
ALTER TABLE IF EXISTS ONLY public.auth_permission DROP CONSTRAINT IF EXISTS auth_permission_pkey;
ALTER TABLE IF EXISTS ONLY public.auth_permission DROP CONSTRAINT IF EXISTS auth_permission_content_type_id_codename_01ab375a_uniq;
ALTER TABLE IF EXISTS ONLY public.auth_group DROP CONSTRAINT IF EXISTS auth_group_pkey;
ALTER TABLE IF EXISTS ONLY public.auth_group_permissions DROP CONSTRAINT IF EXISTS auth_group_permissions_pkey;
ALTER TABLE IF EXISTS ONLY public.auth_group_permissions DROP CONSTRAINT IF EXISTS auth_group_permissions_group_id_permission_id_0cd325b0_uniq;
ALTER TABLE IF EXISTS ONLY public.auth_group DROP CONSTRAINT IF EXISTS auth_group_name_key;
ALTER TABLE IF EXISTS ONLY public.ai_copilot_useraipreference DROP CONSTRAINT IF EXISTS ai_copilot_useraipreference_user_id_key;
ALTER TABLE IF EXISTS ONLY public.ai_copilot_useraipreference DROP CONSTRAINT IF EXISTS ai_copilot_useraipreference_pkey;
ALTER TABLE IF EXISTS ONLY public.ai_copilot_proactiveinsight DROP CONSTRAINT IF EXISTS ai_copilot_proactiveinsight_pkey;
ALTER TABLE IF EXISTS ONLY public.ai_copilot_conversationmessage DROP CONSTRAINT IF EXISTS ai_copilot_conversationmessage_pkey;
ALTER TABLE IF EXISTS ONLY public.accounts_user DROP CONSTRAINT IF EXISTS accounts_user_username_key;
ALTER TABLE IF EXISTS ONLY public.accounts_user_user_permissions DROP CONSTRAINT IF EXISTS accounts_user_user_permissions_pkey;
ALTER TABLE IF EXISTS ONLY public.accounts_user_user_permissions DROP CONSTRAINT IF EXISTS accounts_user_user_permi_user_id_permission_id_2ab516c2_uniq;
ALTER TABLE IF EXISTS ONLY public.accounts_user DROP CONSTRAINT IF EXISTS accounts_user_pkey;
ALTER TABLE IF EXISTS ONLY public.accounts_user_groups DROP CONSTRAINT IF EXISTS accounts_user_groups_user_id_group_id_59c0b32f_uniq;
ALTER TABLE IF EXISTS ONLY public.accounts_user_groups DROP CONSTRAINT IF EXISTS accounts_user_groups_pkey;
ALTER TABLE IF EXISTS ONLY public.accounts_tenant DROP CONSTRAINT IF EXISTS accounts_tenant_pkey;
ALTER TABLE IF EXISTS ONLY public.accounts_tenant DROP CONSTRAINT IF EXISTS accounts_tenant_name_key;
ALTER TABLE IF EXISTS ONLY public.accounts_scopedrole DROP CONSTRAINT IF EXISTS accounts_scopedrole_user_id_group_id_tenant__c33c3cd9_uniq;
ALTER TABLE IF EXISTS ONLY public.accounts_scopedrole DROP CONSTRAINT IF EXISTS accounts_scopedrole_pkey;
ALTER TABLE IF EXISTS ONLY public.accounts_roleassignmentauditlog DROP CONSTRAINT IF EXISTS accounts_roleassignmentauditlog_pkey;
DROP TABLE IF EXISTS public.token_blacklist_outstandingtoken;
DROP TABLE IF EXISTS public.token_blacklist_blacklistedtoken;
DROP TABLE IF EXISTS public.django_session;
DROP TABLE IF EXISTS public.django_migrations;
DROP TABLE IF EXISTS public.django_content_type;
DROP TABLE IF EXISTS public.django_admin_log;
DROP TABLE IF EXISTS public.dataschema_schemachangelog;
DROP TABLE IF EXISTS public.dataschema_datatable;
DROP TABLE IF EXISTS public.dataschema_datarow;
DROP TABLE IF EXISTS public.dataschema_datafield;
DROP TABLE IF EXISTS public.core_project;
DROP TABLE IF EXISTS public.core_module;
DROP TABLE IF EXISTS public.core_feedback;
DROP TABLE IF EXISTS public.auth_permission;
DROP TABLE IF EXISTS public.auth_group_permissions;
DROP TABLE IF EXISTS public.auth_group;
DROP TABLE IF EXISTS public.ai_copilot_useraipreference;
DROP TABLE IF EXISTS public.ai_copilot_proactiveinsight;
DROP TABLE IF EXISTS public.ai_copilot_conversationmessage;
DROP TABLE IF EXISTS public.accounts_user_user_permissions;
DROP TABLE IF EXISTS public.accounts_user_groups;
DROP TABLE IF EXISTS public.accounts_user;
DROP TABLE IF EXISTS public.accounts_tenant;
DROP TABLE IF EXISTS public.accounts_scopedrole;
DROP TABLE IF EXISTS public.accounts_roleassignmentauditlog;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: accounts_roleassignmentauditlog; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts_roleassignmentauditlog (
    id bigint NOT NULL,
    action character varying(16) NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    extra jsonb NOT NULL,
    actor_id bigint,
    group_id integer,
    module_id bigint,
    project_id bigint,
    user_id bigint,
    tenant_id bigint
);


--
-- Name: accounts_roleassignmentauditlog_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.accounts_roleassignmentauditlog ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.accounts_roleassignmentauditlog_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: accounts_scopedrole; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts_scopedrole (
    id bigint NOT NULL,
    created_at timestamp with time zone NOT NULL,
    is_active boolean NOT NULL,
    group_id integer NOT NULL,
    module_id bigint,
    project_id bigint,
    user_id bigint NOT NULL,
    tenant_id bigint NOT NULL
);


--
-- Name: accounts_scopedrole_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.accounts_scopedrole ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.accounts_scopedrole_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: accounts_tenant; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts_tenant (
    id bigint NOT NULL,
    name character varying(128) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: accounts_tenant_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.accounts_tenant ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.accounts_tenant_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: accounts_user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts_user (
    id bigint NOT NULL,
    password character varying(128) NOT NULL,
    last_login timestamp with time zone,
    is_superuser boolean NOT NULL,
    username character varying(150) NOT NULL,
    first_name character varying(150) NOT NULL,
    last_name character varying(150) NOT NULL,
    email character varying(254) NOT NULL,
    is_staff boolean NOT NULL,
    is_active boolean NOT NULL,
    date_joined timestamp with time zone NOT NULL,
    tenant_id bigint NOT NULL
);


--
-- Name: accounts_user_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts_user_groups (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    group_id integer NOT NULL
);


--
-- Name: accounts_user_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.accounts_user_groups ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.accounts_user_groups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: accounts_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.accounts_user ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.accounts_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: accounts_user_user_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts_user_user_permissions (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: accounts_user_user_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.accounts_user_user_permissions ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.accounts_user_user_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ai_copilot_conversationmessage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_copilot_conversationmessage (
    id bigint NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    metadata jsonb NOT NULL,
    created_at timestamp with time zone NOT NULL,
    project_id bigint,
    user_id bigint NOT NULL
);


--
-- Name: ai_copilot_conversationmessage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.ai_copilot_conversationmessage ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.ai_copilot_conversationmessage_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ai_copilot_proactiveinsight; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_copilot_proactiveinsight (
    id bigint NOT NULL,
    type character varying(50) NOT NULL,
    urgency character varying(20) NOT NULL,
    title character varying(200) NOT NULL,
    description text NOT NULL,
    action_label character varying(100) NOT NULL,
    action_url character varying(500) NOT NULL,
    metadata jsonb NOT NULL,
    acknowledged boolean NOT NULL,
    acknowledged_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone,
    project_id bigint,
    user_id bigint NOT NULL
);


--
-- Name: ai_copilot_proactiveinsight_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.ai_copilot_proactiveinsight ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.ai_copilot_proactiveinsight_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ai_copilot_useraipreference; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_copilot_useraipreference (
    id bigint NOT NULL,
    enable_proactive_insights boolean NOT NULL,
    insight_types jsonb NOT NULL,
    response_detail_level character varying(20) NOT NULL,
    allow_conversation_learning boolean NOT NULL,
    panel_collapsed boolean NOT NULL,
    panel_width integer NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    user_id bigint NOT NULL
);


--
-- Name: ai_copilot_useraipreference_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.ai_copilot_useraipreference ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.ai_copilot_useraipreference_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_group; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group (
    id integer NOT NULL,
    name character varying(150) NOT NULL
);


--
-- Name: auth_group_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_group ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_group_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group_permissions (
    id bigint NOT NULL,
    group_id integer NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_group_permissions ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_permission; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_permission (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    content_type_id integer NOT NULL,
    codename character varying(100) NOT NULL
);


--
-- Name: auth_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_permission ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_permission_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: core_feedback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.core_feedback (
    id bigint NOT NULL,
    name character varying(100) NOT NULL,
    email character varying(254) NOT NULL,
    message text NOT NULL,
    rating smallint NOT NULL,
    submitted_at timestamp with time zone NOT NULL,
    CONSTRAINT core_feedback_rating_check CHECK ((rating >= 0))
);


--
-- Name: core_feedback_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.core_feedback ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.core_feedback_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: core_module; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.core_module (
    id bigint NOT NULL,
    name character varying(100) NOT NULL,
    project_id bigint NOT NULL,
    scope smallint NOT NULL,
    CONSTRAINT core_module_scope_check CHECK ((scope >= 0))
);


--
-- Name: core_module_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.core_module ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.core_module_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: core_project; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.core_project (
    id bigint NOT NULL,
    name character varying(100) NOT NULL,
    tenant_id bigint NOT NULL
);


--
-- Name: core_project_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.core_project ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.core_project_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: dataschema_datafield; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dataschema_datafield (
    id bigint NOT NULL,
    name character varying(50) NOT NULL,
    label character varying(100) NOT NULL,
    type character varying(20) NOT NULL,
    default_value jsonb,
    "order" integer NOT NULL,
    description text NOT NULL,
    required boolean NOT NULL,
    options jsonb,
    validation jsonb,
    is_active boolean NOT NULL,
    is_archived boolean NOT NULL,
    version integer NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    created_by_id bigint,
    updated_by_id bigint,
    data_table_id bigint NOT NULL,
    reference_table_id bigint,
    CONSTRAINT dataschema_datafield_order_check CHECK (("order" >= 0)),
    CONSTRAINT dataschema_datafield_version_check CHECK ((version >= 0))
);


--
-- Name: dataschema_datafield_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.dataschema_datafield ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.dataschema_datafield_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: dataschema_datarow; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dataschema_datarow (
    id bigint NOT NULL,
    "values" jsonb NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_archived boolean NOT NULL,
    version integer NOT NULL,
    created_by_id bigint,
    updated_by_id bigint,
    data_table_id bigint NOT NULL,
    CONSTRAINT dataschema_datarow_version_check CHECK ((version >= 0))
);


--
-- Name: dataschema_datarow_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.dataschema_datarow ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.dataschema_datarow_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: dataschema_datatable; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dataschema_datatable (
    id bigint NOT NULL,
    title character varying(255) NOT NULL,
    name character varying(64) NOT NULL,
    description text NOT NULL,
    version integer NOT NULL,
    is_archived boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    created_by_id bigint,
    module_id bigint NOT NULL,
    updated_by_id bigint,
    CONSTRAINT dataschema_datatable_version_check CHECK ((version >= 0))
);


--
-- Name: dataschema_datatable_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.dataschema_datatable ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.dataschema_datatable_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: dataschema_schemachangelog; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dataschema_schemachangelog (
    id bigint NOT NULL,
    action character varying(10) NOT NULL,
    before jsonb,
    after jsonb,
    "timestamp" timestamp with time zone NOT NULL,
    notes text NOT NULL,
    data_field_id bigint,
    data_table_id bigint,
    user_id bigint
);


--
-- Name: dataschema_schemachangelog_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.dataschema_schemachangelog ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.dataschema_schemachangelog_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_admin_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_admin_log (
    id integer NOT NULL,
    action_time timestamp with time zone NOT NULL,
    object_id text,
    object_repr character varying(200) NOT NULL,
    action_flag smallint NOT NULL,
    change_message text NOT NULL,
    content_type_id integer,
    user_id bigint NOT NULL,
    CONSTRAINT django_admin_log_action_flag_check CHECK ((action_flag >= 0))
);


--
-- Name: django_admin_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.django_admin_log ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_admin_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_content_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_content_type (
    id integer NOT NULL,
    app_label character varying(100) NOT NULL,
    model character varying(100) NOT NULL
);


--
-- Name: django_content_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.django_content_type ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_content_type_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_migrations (
    id bigint NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.django_migrations ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_migrations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_session; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_session (
    session_key character varying(40) NOT NULL,
    session_data text NOT NULL,
    expire_date timestamp with time zone NOT NULL
);


--
-- Name: token_blacklist_blacklistedtoken; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token_blacklist_blacklistedtoken (
    id bigint NOT NULL,
    blacklisted_at timestamp with time zone NOT NULL,
    token_id bigint NOT NULL
);


--
-- Name: token_blacklist_blacklistedtoken_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.token_blacklist_blacklistedtoken ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.token_blacklist_blacklistedtoken_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: token_blacklist_outstandingtoken; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token_blacklist_outstandingtoken (
    id bigint NOT NULL,
    token text NOT NULL,
    created_at timestamp with time zone,
    expires_at timestamp with time zone NOT NULL,
    user_id bigint,
    jti character varying(255) NOT NULL
);


--
-- Name: token_blacklist_outstandingtoken_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.token_blacklist_outstandingtoken ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.token_blacklist_outstandingtoken_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Data for Name: accounts_roleassignmentauditlog; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.accounts_roleassignmentauditlog (id, action, "timestamp", extra, actor_id, group_id, module_id, project_id, user_id, tenant_id) FROM stdin;
\.


--
-- Data for Name: accounts_scopedrole; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.accounts_scopedrole (id, created_at, is_active, group_id, module_id, project_id, user_id, tenant_id) FROM stdin;
1	2025-07-08 12:04:47.402858+03	t	1	\N	\N	3	2
2	2025-07-08 12:05:04.09981+03	t	3	\N	1	8	2
5	2025-07-08 13:32:18.32747+03	t	1	\N	\N	3	2
6	2025-07-08 14:58:49.51304+03	t	1	\N	1	4	2
10	2025-07-13 14:07:41.992621+03	t	1	\N	1	9	2
11	2026-01-11 14:20:03.846598+02	t	1	\N	1	3	3
12	2026-01-11 14:20:03.873572+02	t	2	\N	1	6	3
13	2026-01-12 11:20:42.883155+02	t	1	\N	1	3	4
14	2026-01-12 11:20:43.329745+02	t	2	\N	1	6	4
15	2026-01-12 11:20:43.782011+02	t	5	\N	1	10	4
16	2026-01-12 11:31:35.331594+02	t	1	\N	1	3	2
17	2026-01-12 11:31:35.777109+02	t	2	\N	1	6	2
18	2026-01-12 11:31:36.220409+02	t	5	\N	1	10	2
\.


--
-- Data for Name: accounts_tenant; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.accounts_tenant (id, name, created_at) FROM stdin;
1	Default Tenant	2025-07-08 11:31:16.483293+03
2	AAST Carbon	2025-07-08 11:40:23.092439+03
3	local	2026-01-11 13:59:27.14182+02
4	AAST	2026-01-12 11:20:42.409766+02
\.


--
-- Data for Name: accounts_user; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.accounts_user (id, password, last_login, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined, tenant_id) FROM stdin;
8	pbkdf2_sha256$1000000$BOHEzALHGi8Y5DcACVWpb4$AMVvlqeQwSKqv1Vx9EfCdVqvhtGwye1eflxbhjTEIIo=	\N	f	auditor1				f	t	2025-07-08 12:01:59+03	2
7	pbkdf2_sha256$1000000$t3p3vcxOfiVYadly4Ygxyi$ueaEIlSw+/4txXy/McwQcc4Nalm2HN2bnWCBYyPrL40=	\N	f	dataowner2				f	t	2025-07-08 12:01:27+03	2
6	pbkdf2_sha256$1000000$LpzYBEOEb2kUSDLGDJ8nvd$DvQWpvCW3PTWfwojxL3yrFgCYNxxxOkSSYKzQ6JlQ0U=	\N	f	dataowner1			dataowner1@aastmt.edu.eg	f	t	2025-07-08 11:52:39+03	2
10	pbkdf2_sha256$1000000$p5fjPc8dRdmhUnzefZKawk$wFIA3u7U6weucZZ75VyhIGXhjmfDqMPI978DE2qq9SM=	\N	f	dataviewer1			dataviewer1@aastmt.edu.eg	f	t	2026-01-12 11:20:43.332756+02	2
3	pbkdf2_sha256$1000000$EPGBOUdL5M4mhosHi49euQ$nbrH6BypCqOjOc1H4ixRnCTelpg/C40z/uJzuyJHivg=	2026-01-12 11:32:39.073439+02	t	admin			admin@aastmt.edu.eg	t	t	2025-07-08 11:32:42+03	2
9	pbkdf2_sha256$1000000$iJNws2Za5OskqS7AccEjaM$jiNXKK4ri8okLTO5lVW5JqxJELhGC+YBp987cIpFoCs=	\N	f	admin1				f	t	2025-07-13 14:06:48+03	2
4	pbkdf2_sha256$1000000$PVY7J3lagZQ22Vp4k8W1JL$S+Sz0haEgiQqF+ABBwV91PMW1u2IqDk5XFZ2cfIgxi4=	2025-08-04 14:55:23.914752+03	t	ahmed			ahmed.se@gmail.com	t	t	2025-07-08 11:33:29+03	2
\.


--
-- Data for Name: accounts_user_groups; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.accounts_user_groups (id, user_id, group_id) FROM stdin;
1	8	3
3	7	2
4	3	1
5	3	4
8	9	1
\.


--
-- Data for Name: accounts_user_user_permissions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.accounts_user_user_permissions (id, user_id, permission_id) FROM stdin;
\.


--
-- Data for Name: ai_copilot_conversationmessage; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.ai_copilot_conversationmessage (id, role, content, metadata, created_at, project_id, user_id) FROM stdin;
\.


--
-- Data for Name: ai_copilot_proactiveinsight; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.ai_copilot_proactiveinsight (id, type, urgency, title, description, action_label, action_url, metadata, acknowledged, acknowledged_at, created_at, expires_at, project_id, user_id) FROM stdin;
\.


--
-- Data for Name: ai_copilot_useraipreference; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.ai_copilot_useraipreference (id, enable_proactive_insights, insight_types, response_detail_level, allow_conversation_learning, panel_collapsed, panel_width, updated_at, user_id) FROM stdin;
\.


--
-- Data for Name: auth_group; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.auth_group (id, name) FROM stdin;
1	admins_group
2	dataowners_group
3	auditors_group
4	admin
5	viewers_group
\.


--
-- Data for Name: auth_group_permissions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.auth_group_permissions (id, group_id, permission_id) FROM stdin;
1	1	1
2	1	2
3	1	3
4	1	4
5	1	5
6	1	6
7	1	7
8	1	8
9	1	9
10	1	10
11	1	11
12	1	12
13	1	13
14	1	14
15	1	15
16	1	16
17	1	17
18	1	18
19	1	19
20	1	20
21	1	21
22	1	22
23	1	23
24	1	24
25	1	25
26	1	26
27	1	27
28	1	28
29	1	29
30	1	30
31	1	31
32	1	32
33	1	33
34	1	34
35	1	35
36	1	36
37	1	37
38	1	38
39	1	39
40	1	40
41	1	41
42	1	42
43	1	43
44	1	44
45	1	45
46	1	46
47	1	47
48	1	48
49	1	49
50	1	50
51	1	51
52	1	52
53	1	53
54	1	54
55	1	55
56	1	56
57	1	57
58	1	58
59	1	59
60	1	60
61	2	32
62	2	36
63	2	28
64	2	29
65	2	30
66	2	31
67	3	32
68	3	36
69	3	28
70	3	29
71	3	30
72	3	31
73	4	1
74	4	2
75	4	3
76	4	4
77	4	5
78	4	6
79	4	7
80	4	8
81	4	9
82	4	10
83	4	11
84	4	12
85	4	13
86	4	14
87	4	15
88	4	16
89	4	17
90	4	18
91	4	19
92	4	20
93	4	21
94	4	22
95	4	23
96	4	24
97	4	25
98	4	26
99	4	27
100	4	28
101	4	29
102	4	30
103	4	31
104	4	32
105	4	33
106	4	34
107	4	35
108	4	36
109	4	37
110	4	38
111	4	39
112	4	40
113	4	41
114	4	42
115	4	43
116	4	44
117	4	45
118	4	46
119	4	47
120	4	48
121	4	49
122	4	50
123	4	51
124	4	52
125	4	53
126	4	54
127	4	55
128	4	56
129	4	57
130	4	58
131	4	59
132	4	60
\.


--
-- Data for Name: auth_permission; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.auth_permission (id, name, content_type_id, codename) FROM stdin;
1	Can add Scoped Role Assignment	1	add_scopedrole
2	Can change Scoped Role Assignment	1	change_scopedrole
3	Can delete Scoped Role Assignment	1	delete_scopedrole
4	Can view Scoped Role Assignment	1	view_scopedrole
5	Can add tenant	2	add_tenant
6	Can change tenant	2	change_tenant
7	Can delete tenant	2	delete_tenant
8	Can view tenant	2	view_tenant
9	Can add user	3	add_user
10	Can change user	3	change_user
11	Can delete user	3	delete_user
12	Can view user	3	view_user
13	Can add role assignment audit log	4	add_roleassignmentauditlog
14	Can change role assignment audit log	4	change_roleassignmentauditlog
15	Can delete role assignment audit log	4	delete_roleassignmentauditlog
16	Can view role assignment audit log	4	view_roleassignmentauditlog
17	Can add Project	5	add_project
18	Can change Project	5	change_project
19	Can delete Project	5	delete_project
20	Can view Project	5	view_project
21	Can add Module	6	add_module
22	Can change Module	6	change_module
23	Can delete Module	6	delete_module
24	Can view Module	6	view_module
25	Can add data table	7	add_datatable
26	Can change data table	7	change_datatable
27	Can delete data table	7	delete_datatable
28	Can view data table	7	view_datatable
29	Can add data row	8	add_datarow
30	Can change data row	8	change_datarow
31	Can delete data row	8	delete_datarow
32	Can view data row	8	view_datarow
33	Can add data field	9	add_datafield
34	Can change data field	9	change_datafield
35	Can delete data field	9	delete_datafield
36	Can view data field	9	view_datafield
37	Can add schema change log	10	add_schemachangelog
38	Can change schema change log	10	change_schemachangelog
39	Can delete schema change log	10	delete_schemachangelog
40	Can view schema change log	10	view_schemachangelog
41	Can add log entry	11	add_logentry
42	Can change log entry	11	change_logentry
43	Can delete log entry	11	delete_logentry
44	Can view log entry	11	view_logentry
45	Can add permission	12	add_permission
46	Can change permission	12	change_permission
47	Can delete permission	12	delete_permission
48	Can view permission	12	view_permission
49	Can add group	13	add_group
50	Can change group	13	change_group
51	Can delete group	13	delete_group
52	Can view group	13	view_group
53	Can add content type	14	add_contenttype
54	Can change content type	14	change_contenttype
55	Can delete content type	14	delete_contenttype
56	Can view content type	14	view_contenttype
57	Can add session	15	add_session
58	Can change session	15	change_session
59	Can delete session	15	delete_session
60	Can view session	15	view_session
61	Can add Feedback	16	add_feedback
62	Can change Feedback	16	change_feedback
63	Can delete Feedback	16	delete_feedback
64	Can view Feedback	16	view_feedback
65	Can add blacklisted token	17	add_blacklistedtoken
66	Can change blacklisted token	17	change_blacklistedtoken
67	Can delete blacklisted token	17	delete_blacklistedtoken
68	Can view blacklisted token	17	view_blacklistedtoken
69	Can add outstanding token	18	add_outstandingtoken
70	Can change outstanding token	18	change_outstandingtoken
71	Can delete outstanding token	18	delete_outstandingtoken
72	Can view outstanding token	18	view_outstandingtoken
73	Can add user ai preference	19	add_useraipreference
74	Can change user ai preference	19	change_useraipreference
75	Can delete user ai preference	19	delete_useraipreference
76	Can view user ai preference	19	view_useraipreference
77	Can add proactive insight	20	add_proactiveinsight
78	Can change proactive insight	20	change_proactiveinsight
79	Can delete proactive insight	20	delete_proactiveinsight
80	Can view proactive insight	20	view_proactiveinsight
81	Can add conversation message	21	add_conversationmessage
82	Can change conversation message	21	change_conversationmessage
83	Can delete conversation message	21	delete_conversationmessage
84	Can view conversation message	21	view_conversationmessage
\.


--
-- Data for Name: core_feedback; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.core_feedback (id, name, email, message, rating, submitted_at) FROM stdin;
1	aaa	ahmed.se@gmail.com	wewew	5	2025-07-13 15:13:05.488331+03
2	aaaa	ahmed.se@gmail.com	aaa	5	2025-07-13 15:25:10.199352+03
\.


--
-- Data for Name: core_module; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.core_module (id, name, project_id, scope) FROM stdin;
5	Stationary Combustion	1	1
6	Mobile Combustion	1	1
7	Fugitive Emissions	1	1
8	Purchased Energy	1	2
9	Consumable Purchased goods and services	1	3
10	Capital Goods	1	3
11	Fertilizers	1	3
12	Fuel & Energy Related Emissions	1	3
13	Water Usage/Waste	1	3
14	Annual Commuting	1	3
15	Waste	1	3
16	Business travel	1	3
17	Upstream transportation and distribution Purchased Goods	1	3
18	Upstream Leased Assets	1	3
\.


--
-- Data for Name: core_project; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.core_project (id, name, tenant_id) FROM stdin;
1	AAST Carbon	2
\.


--
-- Data for Name: dataschema_datafield; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.dataschema_datafield (id, name, label, type, default_value, "order", description, required, options, validation, is_active, is_archived, version, created_at, updated_at, created_by_id, updated_by_id, data_table_id, reference_table_id) FROM stdin;
46	reporting_month	Month	select	\N	1		t	{"choices": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]}	\N	t	f	1	2026-01-11 15:36:49.541471+02	2026-01-11 15:36:49.541485+02	3	3	13	\N
47	vehicle_type	Vehicle Type	select	\N	2		t	{"choices": ["Staff Bus", "Administrative Car", "Maintenance Vehicle", "Security Patrol"]}	\N	t	f	1	2026-01-11 15:36:49.546371+02	2026-01-11 15:36:49.546384+02	3	3	13	\N
48	fuel_type	Fuel Type	select	\N	3		t	{"choices": ["Diesel", "Gasoline"]}	\N	t	f	1	2026-01-11 15:36:49.551641+02	2026-01-11 15:36:49.551655+02	3	3	13	\N
12	date	Date	date	\N	0	Date	t	\N	\N	t	f	1	2025-08-04 13:44:06.294811+03	2025-08-04 13:44:06.29482+03	\N	\N	6	\N
13	quantity	Quantity	number	\N	0	Quantity	t	\N	\N	t	f	1	2025-08-04 13:44:16.408967+03	2025-08-04 13:44:16.408976+03	\N	\N	6	\N
15	date	Date	date	\N	0	Date	t	\N	\N	t	f	1	2025-08-04 13:46:14.322937+03	2025-08-04 13:46:14.322948+03	\N	\N	7	\N
16	quantity	Quantity	number	\N	0	Quantity	t	\N	\N	t	f	1	2025-08-04 13:46:35.359057+03	2025-08-04 13:46:35.359067+03	\N	\N	7	\N
17	data_unit	Data Unit	select	\N	0	Data Unit	f	[{"label": "L", "value": "L"}]	\N	t	f	1	2025-08-04 13:47:14.872304+03	2025-08-04 13:47:14.872315+03	\N	\N	7	\N
14	data_unit	Data Unit	select	\N	0		f	[{"label": "m³", "value": "m³"}]	\N	t	f	1	2025-08-04 13:44:55.641956+03	2025-08-04 13:47:33.478592+03	\N	\N	6	\N
18	reporting_year	Reporting Year	number	\N	0		t	\N	\N	t	f	1	2026-01-11 15:36:48.783993+02	2026-01-11 15:36:48.784009+02	3	3	10	\N
19	reporting_month	Month	select	\N	1		t	{"choices": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]}	\N	t	f	1	2026-01-11 15:36:48.791121+02	2026-01-11 15:36:48.791136+02	3	3	10	\N
20	campus	Campus	select	\N	2		t	{"choices": ["Smart Village", "Alexandria", "Cairo"]}	\N	t	f	1	2026-01-11 15:36:48.797497+02	2026-01-11 15:36:48.797512+02	3	3	10	\N
21	equipment_id	Equipment ID	string	\N	3		f	\N	\N	t	f	1	2026-01-11 15:36:48.80316+02	2026-01-11 15:36:48.803176+02	3	3	10	\N
22	fuel_type	Fuel Type	select	\N	4		t	{"choices": ["Diesel", "Natural Gas", "LPG", "Gasoline"]}	\N	t	f	1	2026-01-11 15:36:48.80961+02	2026-01-11 15:36:48.809624+02	3	3	10	\N
23	quantity	Quantity Consumed	number	\N	5		t	\N	\N	t	f	1	2026-01-11 15:36:48.815019+02	2026-01-11 15:36:48.815033+02	3	3	10	\N
24	unit	Unit	select	\N	6		t	{"choices": ["Liters", "m³", "kg"]}	\N	t	f	1	2026-01-11 15:36:48.820535+02	2026-01-11 15:36:48.820549+02	3	3	10	\N
25	co2e_emissions	CO2e Emissions (kg)	number	\N	7		f	\N	\N	t	f	1	2026-01-11 15:36:48.825566+02	2026-01-11 15:36:48.825582+02	3	3	10	\N
26	notes	Notes	text	\N	8		f	\N	\N	t	f	1	2026-01-11 15:36:48.829969+02	2026-01-11 15:36:48.829982+02	3	3	10	\N
27	reporting_year	Reporting Year	number	\N	0		t	\N	\N	t	f	1	2026-01-11 15:36:48.841314+02	2026-01-11 15:36:48.841327+02	3	3	11	\N
28	reporting_month	Month	select	\N	1		t	{"choices": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]}	\N	t	f	1	2026-01-11 15:36:48.847492+02	2026-01-11 15:36:48.84751+02	3	3	11	\N
29	campus	Campus	select	\N	2		t	{"choices": ["Smart Village", "Alexandria", "Cairo"]}	\N	t	f	1	2026-01-11 15:36:48.853305+02	2026-01-11 15:36:48.853319+02	3	3	11	\N
30	equipment_id	Equipment ID	string	\N	3		f	\N	\N	t	f	1	2026-01-11 15:36:48.858201+02	2026-01-11 15:36:48.858216+02	3	3	11	\N
31	fuel_type	Fuel Type	select	\N	4		t	{"choices": ["Diesel", "Natural Gas", "LPG", "Gasoline"]}	\N	t	f	1	2026-01-11 15:36:48.863034+02	2026-01-11 15:36:48.863049+02	3	3	11	\N
32	quantity	Quantity Consumed	number	\N	5		t	\N	\N	t	f	1	2026-01-11 15:36:48.869623+02	2026-01-11 15:36:48.869638+02	3	3	11	\N
33	unit	Unit	select	\N	6		t	{"choices": ["Liters", "m³", "kg"]}	\N	t	f	1	2026-01-11 15:36:48.874586+02	2026-01-11 15:36:48.8746+02	3	3	11	\N
34	co2e_emissions	CO2e Emissions (kg)	number	\N	7		f	\N	\N	t	f	1	2026-01-11 15:36:48.880256+02	2026-01-11 15:36:48.880273+02	3	3	11	\N
35	notes	Notes	text	\N	8		f	\N	\N	t	f	1	2026-01-11 15:36:48.886167+02	2026-01-11 15:36:48.886183+02	3	3	11	\N
36	reporting_year	Reporting Year	number	\N	0		t	\N	\N	t	f	1	2026-01-11 15:36:48.9014+02	2026-01-11 15:36:48.901417+02	3	3	12	\N
37	reporting_month	Month	select	\N	1		t	{"choices": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]}	\N	t	f	1	2026-01-11 15:36:48.906699+02	2026-01-11 15:36:48.906714+02	3	3	12	\N
38	campus	Campus	select	\N	2		t	{"choices": ["Smart Village", "Alexandria", "Cairo"]}	\N	t	f	1	2026-01-11 15:36:48.91285+02	2026-01-11 15:36:48.912866+02	3	3	12	\N
39	equipment_id	Equipment ID	string	\N	3		f	\N	\N	t	f	1	2026-01-11 15:36:48.918483+02	2026-01-11 15:36:48.918497+02	3	3	12	\N
40	fuel_type	Fuel Type	select	\N	4		t	{"choices": ["Diesel", "Natural Gas", "LPG", "Gasoline"]}	\N	t	f	1	2026-01-11 15:36:48.925122+02	2026-01-11 15:36:48.925137+02	3	3	12	\N
41	quantity	Quantity Consumed	number	\N	5		t	\N	\N	t	f	1	2026-01-11 15:36:48.931244+02	2026-01-11 15:36:48.931259+02	3	3	12	\N
42	unit	Unit	select	\N	6		t	{"choices": ["Liters", "m³", "kg"]}	\N	t	f	1	2026-01-11 15:36:48.936396+02	2026-01-11 15:36:48.936412+02	3	3	12	\N
43	co2e_emissions	CO2e Emissions (kg)	number	\N	7		f	\N	\N	t	f	1	2026-01-11 15:36:48.943412+02	2026-01-11 15:36:48.94343+02	3	3	12	\N
44	notes	Notes	text	\N	8		f	\N	\N	t	f	1	2026-01-11 15:36:48.949024+02	2026-01-11 15:36:48.94904+02	3	3	12	\N
45	reporting_year	Reporting Year	number	\N	0		t	\N	\N	t	f	1	2026-01-11 15:36:49.53599+02	2026-01-11 15:36:49.536029+02	3	3	13	\N
49	quantity_liters	Quantity (Liters)	number	\N	4		t	\N	\N	t	f	1	2026-01-11 15:36:49.55841+02	2026-01-11 15:36:49.558425+02	3	3	13	\N
50	distance_km	Distance (km)	number	\N	5		f	\N	\N	t	f	1	2026-01-11 15:36:49.563416+02	2026-01-11 15:36:49.56343+02	3	3	13	\N
51	co2e_emissions	CO2e Emissions (kg)	number	\N	6		f	\N	\N	t	f	1	2026-01-11 15:36:49.568493+02	2026-01-11 15:36:49.568519+02	3	3	13	\N
52	reporting_year	Reporting Year	number	\N	0		t	\N	\N	t	f	1	2026-01-11 15:36:51.121912+02	2026-01-11 15:36:51.121927+02	3	3	14	\N
53	equipment_type	Equipment Type	select	\N	1		t	{"choices": ["Split AC Units", "Central Chiller", "VRF System", "Refrigerators"]}	\N	t	f	1	2026-01-11 15:36:51.128155+02	2026-01-11 15:36:51.128169+02	3	3	14	\N
54	refrigerant_type	Refrigerant Type	select	\N	2		t	{"choices": ["R-134a", "R-410A", "R-407C", "R-22"]}	\N	t	f	1	2026-01-11 15:36:51.133597+02	2026-01-11 15:36:51.133633+02	3	3	14	\N
55	initial_charge_kg	Initial Charge (kg)	number	\N	3		t	\N	\N	t	f	1	2026-01-11 15:36:51.138842+02	2026-01-11 15:36:51.138856+02	3	3	14	\N
56	leakage_rate_pct	Leakage Rate (%)	number	\N	4		t	\N	\N	t	f	1	2026-01-11 15:36:51.144695+02	2026-01-11 15:36:51.144709+02	3	3	14	\N
57	quantity_leaked_kg	Quantity Leaked (kg)	number	\N	5		f	\N	\N	t	f	1	2026-01-11 15:36:51.150188+02	2026-01-11 15:36:51.150204+02	3	3	14	\N
58	co2e_emissions	CO2e Emissions (kg)	number	\N	6		f	\N	\N	t	f	1	2026-01-11 15:36:51.156466+02	2026-01-11 15:36:51.156481+02	3	3	14	\N
59	system_type	System Type	select	\N	1		t	{"choices": ["CO2", "FM200", "Halon"]}	\N	t	f	1	2026-01-11 15:36:51.250909+02	2026-01-11 15:36:51.250926+02	3	3	14	\N
60	location	Location	string	\N	2		t	\N	\N	t	f	1	2026-01-11 15:36:51.257332+02	2026-01-11 15:36:51.257359+02	3	3	14	\N
61	quantity_released_kg	Quantity Released (kg)	number	\N	3		t	\N	\N	t	f	1	2026-01-11 15:36:51.264763+02	2026-01-11 15:36:51.26478+02	3	3	14	\N
62	reporting_year	Reporting Year	number	\N	0		t	\N	\N	t	f	1	2026-01-11 15:36:51.303281+02	2026-01-11 15:36:51.303297+02	3	3	16	\N
63	reporting_month	Month	select	\N	1		t	{"choices": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]}	\N	t	f	1	2026-01-11 15:36:51.308807+02	2026-01-11 15:36:51.308822+02	3	3	16	\N
64	building	Building	select	\N	2		t	{"choices": ["Building 401", "Building 2401", "Other"]}	\N	t	f	1	2026-01-11 15:36:51.314041+02	2026-01-11 15:36:51.314056+02	3	3	16	\N
65	meter_reading_start	Meter Start	number	\N	3		f	\N	\N	t	f	1	2026-01-11 15:36:51.320176+02	2026-01-11 15:36:51.320194+02	3	3	16	\N
66	meter_reading_end	Meter End	number	\N	4		f	\N	\N	t	f	1	2026-01-11 15:36:51.326874+02	2026-01-11 15:36:51.326888+02	3	3	16	\N
67	consumption_kwh	Consumption (kWh)	number	\N	5		t	\N	\N	t	f	1	2026-01-11 15:36:51.331236+02	2026-01-11 15:36:51.331247+02	3	3	16	\N
68	grid_emission_factor	Grid EF (kg CO2e/kWh)	number	\N	6		f	\N	\N	t	f	1	2026-01-11 15:36:51.336124+02	2026-01-11 15:36:51.336138+02	3	3	16	\N
69	co2e_emissions	CO2e Emissions (kg)	number	\N	7		f	\N	\N	t	f	1	2026-01-11 15:36:51.341003+02	2026-01-11 15:36:51.341017+02	3	3	16	\N
70	reporting_year	Reporting Year	number	\N	0		t	\N	\N	t	f	1	2026-01-11 15:36:51.35343+02	2026-01-11 15:36:51.353446+02	3	3	17	\N
71	reporting_month	Month	select	\N	1		t	{"choices": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]}	\N	t	f	1	2026-01-11 15:36:51.358234+02	2026-01-11 15:36:51.358249+02	3	3	17	\N
72	building	Building	select	\N	2		t	{"choices": ["Building 2401-1", "Building 2401-2"]}	\N	t	f	1	2026-01-11 15:36:51.363084+02	2026-01-11 15:36:51.363098+02	3	3	17	\N
73	consumption_tr	Consumption (TR)	number	\N	3		t	\N	\N	t	f	1	2026-01-11 15:36:51.368106+02	2026-01-11 15:36:51.36812+02	3	3	17	\N
74	co2e_emissions	CO2e Emissions (kg)	number	\N	4		f	\N	\N	t	f	1	2026-01-11 15:36:51.37332+02	2026-01-11 15:36:51.373334+02	3	3	17	\N
75	reporting_year	Reporting Year	number	\N	0		t	\N	\N	t	f	1	2026-01-11 15:36:52.426982+02	2026-01-11 15:36:52.426997+02	3	3	18	\N
76	reporting_month	Month	select	\N	1		t	{"choices": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]}	\N	t	f	1	2026-01-11 15:36:52.434626+02	2026-01-11 15:36:52.43464+02	3	3	18	\N
77	source	Source	select	\N	2		t	{"choices": ["Municipal Supply", "Well Water", "Recycled"]}	\N	t	f	1	2026-01-11 15:36:52.440161+02	2026-01-11 15:36:52.440175+02	3	3	18	\N
78	consumption_m3	Consumption (m³)	number	\N	3		t	\N	\N	t	f	1	2026-01-11 15:36:52.444837+02	2026-01-11 15:36:52.444851+02	3	3	18	\N
79	wastewater_m3	Wastewater (m³)	number	\N	4		f	\N	\N	t	f	1	2026-01-11 15:36:52.450011+02	2026-01-11 15:36:52.450025+02	3	3	18	\N
80	co2e_emissions	CO2e Emissions (kg)	number	\N	5		f	\N	\N	t	f	1	2026-01-11 15:36:52.457532+02	2026-01-11 15:36:52.457547+02	3	3	18	\N
81	reporting_year	Reporting Year	number	\N	0		t	\N	\N	t	f	1	2026-01-11 15:36:52.73544+02	2026-01-11 15:36:52.735455+02	3	3	19	\N
82	commuter_type	Commuter Type	select	\N	1		t	{"choices": ["Staff", "Faculty", "Student"]}	\N	t	f	1	2026-01-11 15:36:52.74129+02	2026-01-11 15:36:52.741304+02	3	3	19	\N
83	transport_mode	Transport Mode	select	\N	2		t	{"choices": ["Private Car", "University Bus", "Public Bus", "Metro", "Carpool", "Bicycle", "Walking"]}	\N	t	f	1	2026-01-11 15:36:52.747422+02	2026-01-11 15:36:52.747437+02	3	3	19	\N
84	headcount	Number of Commuters	number	\N	3		t	\N	\N	t	f	1	2026-01-11 15:36:52.752488+02	2026-01-11 15:36:52.752502+02	3	3	19	\N
85	avg_distance_km	Avg One-Way Distance (km)	number	\N	4		t	\N	\N	t	f	1	2026-01-11 15:36:52.757279+02	2026-01-11 15:36:52.757293+02	3	3	19	\N
86	working_days	Working Days/Year	number	\N	5		t	\N	\N	t	f	1	2026-01-11 15:36:52.761856+02	2026-01-11 15:36:52.761881+02	3	3	19	\N
87	total_km	Total km/Year	number	\N	6		f	\N	\N	t	f	1	2026-01-11 15:36:52.770522+02	2026-01-11 15:36:52.770538+02	3	3	19	\N
88	co2e_emissions	CO2e Emissions (kg)	number	\N	7		f	\N	\N	t	f	1	2026-01-11 15:36:52.775185+02	2026-01-11 15:36:52.775198+02	3	3	19	\N
89	reporting_year	Reporting Year	number	\N	0		t	\N	\N	t	f	1	2026-01-11 15:36:53.000591+02	2026-01-11 15:36:53.000608+02	3	3	20	\N
90	reporting_month	Month	select	\N	1		t	{"choices": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]}	\N	t	f	1	2026-01-11 15:36:53.006773+02	2026-01-11 15:36:53.006787+02	3	3	20	\N
91	waste_type	Waste Type	select	\N	2		t	{"choices": ["General Waste", "Paper/Cardboard", "Plastic", "E-Waste", "Food Waste", "Hazardous"]}	\N	t	f	1	2026-01-11 15:36:53.012078+02	2026-01-11 15:36:53.012098+02	3	3	20	\N
92	disposal_method	Disposal Method	select	\N	3		t	{"choices": ["Landfill", "Recycled", "Composted", "Incinerated", "Special Treatment"]}	\N	t	f	1	2026-01-11 15:36:53.017543+02	2026-01-11 15:36:53.017556+02	3	3	20	\N
93	quantity_kg	Quantity (kg)	number	\N	4		t	\N	\N	t	f	1	2026-01-11 15:36:53.023826+02	2026-01-11 15:36:53.023839+02	3	3	20	\N
94	co2e_emissions	CO2e Emissions (kg)	number	\N	5		f	\N	\N	t	f	1	2026-01-11 15:36:53.030015+02	2026-01-11 15:36:53.030031+02	3	3	20	\N
95	reporting_year	Reporting Year	number	\N	0		t	\N	\N	t	f	1	2026-01-11 15:36:55.106163+02	2026-01-11 15:36:55.106182+02	3	3	21	\N
96	quarter	Quarter	select	\N	1		t	{"choices": ["Q1", "Q2", "Q3", "Q4"]}	\N	t	f	1	2026-01-11 15:36:55.114698+02	2026-01-11 15:36:55.114713+02	3	3	21	\N
97	travel_type	Travel Type	select	\N	2		t	{"choices": ["Domestic", "Regional (Middle East)", "International"]}	\N	t	f	1	2026-01-11 15:36:55.119495+02	2026-01-11 15:36:55.119506+02	3	3	21	\N
98	purpose	Purpose	select	\N	3		t	{"choices": ["Conference", "Research Collaboration", "Administrative", "Training"]}	\N	t	f	1	2026-01-11 15:36:55.124769+02	2026-01-11 15:36:55.124784+02	3	3	21	\N
99	number_of_trips	Number of Trips	number	\N	4		t	\N	\N	t	f	1	2026-01-11 15:36:55.132745+02	2026-01-11 15:36:55.132759+02	3	3	21	\N
100	avg_distance_km	Avg Distance (km)	number	\N	5		t	\N	\N	t	f	1	2026-01-11 15:36:55.137822+02	2026-01-11 15:36:55.137841+02	3	3	21	\N
101	total_km	Total km	number	\N	6		f	\N	\N	t	f	1	2026-01-11 15:36:55.143797+02	2026-01-11 15:36:55.143811+02	3	3	21	\N
102	co2e_emissions	CO2e Emissions (kg)	number	\N	7		f	\N	\N	t	f	1	2026-01-11 15:36:55.149007+02	2026-01-11 15:36:55.149021+02	3	3	21	\N
103	reporting_year	Reporting Year	number	\N	0		t	\N	\N	t	f	1	2026-01-11 15:36:55.738311+02	2026-01-11 15:36:55.738326+02	3	3	22	\N
104	category	Category	select	\N	1		t	{"choices": ["Paper Products", "Printer Ink/Toner", "Hygiene Supplies", "Cleaning Products", "Lab Consumables"]}	\N	t	f	1	2026-01-11 15:36:55.743669+02	2026-01-11 15:36:55.743689+02	3	3	22	\N
105	item_description	Item Description	string	\N	2		f	\N	\N	t	f	1	2026-01-11 15:36:55.748876+02	2026-01-11 15:36:55.74889+02	3	3	22	\N
106	quantity	Quantity	number	\N	3		t	\N	\N	t	f	1	2026-01-11 15:36:55.753662+02	2026-01-11 15:36:55.753676+02	3	3	22	\N
107	unit	Unit	select	\N	4		t	{"choices": ["kg", "Units", "Liters", "Boxes"]}	\N	t	f	1	2026-01-11 15:36:55.758762+02	2026-01-11 15:36:55.758779+02	3	3	22	\N
108	spend_egp	Spend (EGP)	number	\N	5		f	\N	\N	t	f	1	2026-01-11 15:36:55.764542+02	2026-01-11 15:36:55.764558+02	3	3	22	\N
109	co2e_emissions	CO2e Emissions (kg)	number	\N	6		f	\N	\N	t	f	1	2026-01-11 15:36:55.771099+02	2026-01-11 15:36:55.771112+02	3	3	22	\N
110	reporting_year	Reporting Year	number	\N	0		t	\N	\N	t	f	1	2026-01-11 15:36:55.965316+02	2026-01-11 15:36:55.965331+02	3	3	23	\N
111	reporting_period	Reporting Period	string	\N	1		t	\N	\N	t	f	1	2026-01-11 15:36:55.97039+02	2026-01-11 15:36:55.970406+02	3	3	23	\N
112	scope_1_total	Scope 1 Total (tCO2e)	number	\N	2		t	\N	\N	t	f	1	2026-01-11 15:36:55.977729+02	2026-01-11 15:36:55.977746+02	3	3	23	\N
113	scope_2_total	Scope 2 Total (tCO2e)	number	\N	3		t	\N	\N	t	f	1	2026-01-11 15:36:55.983764+02	2026-01-11 15:36:55.983781+02	3	3	23	\N
114	scope_3_total	Scope 3 Total (tCO2e)	number	\N	4		t	\N	\N	t	f	1	2026-01-11 15:36:55.991056+02	2026-01-11 15:36:55.991075+02	3	3	23	\N
115	total_emissions	Total Emissions (tCO2e)	number	\N	5		t	\N	\N	t	f	1	2026-01-11 15:36:55.99655+02	2026-01-11 15:36:55.996564+02	3	3	23	\N
116	intensity_per_student	Intensity (tCO2e/student)	number	\N	6		f	\N	\N	t	f	1	2026-01-11 15:36:56.002286+02	2026-01-11 15:36:56.0023+02	3	3	23	\N
117	intensity_per_sqm	Intensity (tCO2e/m²)	number	\N	7		f	\N	\N	t	f	1	2026-01-11 15:36:56.007319+02	2026-01-11 15:36:56.007337+02	3	3	23	\N
118	verification_status	Verification Status	select	\N	8		f	{"choices": ["Draft", "Pending Review", "Verified", "Published"]}	\N	t	f	1	2026-01-11 15:36:56.012797+02	2026-01-11 15:36:56.012811+02	3	3	23	\N
119	notes	Notes	text	\N	9		f	\N	\N	t	f	1	2026-01-11 15:36:56.017737+02	2026-01-11 15:36:56.017752+02	3	3	23	\N
\.


--
-- Data for Name: dataschema_datarow; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.dataschema_datarow (id, "values", created_at, updated_at, is_archived, version, created_by_id, updated_by_id, data_table_id) FROM stdin;
12	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 95, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 254.6, "reporting_year": 2020, "reporting_month": "January"}	2026-01-11 15:36:48.954128+02	2026-01-11 15:36:48.954145+02	f	1	3	3	10
13	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 101, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 270.68, "reporting_year": 2020, "reporting_month": "February"}	2026-01-11 15:36:48.962614+02	2026-01-11 15:36:48.962631+02	f	1	3	3	10
14	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 121, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 324.28, "reporting_year": 2020, "reporting_month": "March"}	2026-01-11 15:36:48.966492+02	2026-01-11 15:36:48.966508+02	f	1	3	3	10
15	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 137, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 367.16, "reporting_year": 2020, "reporting_month": "April"}	2026-01-11 15:36:48.970383+02	2026-01-11 15:36:48.970399+02	f	1	3	3	10
16	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 150, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 402.0, "reporting_year": 2020, "reporting_month": "May"}	2026-01-11 15:36:48.975461+02	2026-01-11 15:36:48.975477+02	f	1	3	3	10
17	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 179, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 479.72, "reporting_year": 2020, "reporting_month": "June"}	2026-01-11 15:36:48.97948+02	2026-01-11 15:36:48.979495+02	f	1	3	3	10
18	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 213, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 570.84, "reporting_year": 2020, "reporting_month": "July"}	2026-01-11 15:36:48.983207+02	2026-01-11 15:36:48.98322+02	f	1	3	3	10
19	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 204, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 546.72, "reporting_year": 2020, "reporting_month": "August"}	2026-01-11 15:36:48.988389+02	2026-01-11 15:36:48.988406+02	f	1	3	3	10
20	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 158, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 423.44, "reporting_year": 2020, "reporting_month": "September"}	2026-01-11 15:36:48.992935+02	2026-01-11 15:36:48.99295+02	f	1	3	3	10
21	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 141, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 377.88, "reporting_year": 2020, "reporting_month": "October"}	2026-01-11 15:36:48.996528+02	2026-01-11 15:36:48.996542+02	f	1	3	3	10
22	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 127, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 340.36, "reporting_year": 2020, "reporting_month": "November"}	2026-01-11 15:36:49.000035+02	2026-01-11 15:36:49.000055+02	f	1	3	3	10
23	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 100, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 268.0, "reporting_year": 2020, "reporting_month": "December"}	2026-01-11 15:36:49.004359+02	2026-01-11 15:36:49.004387+02	f	1	3	3	10
24	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 96, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 257.28, "reporting_year": 2021, "reporting_month": "January"}	2026-01-11 15:36:49.008788+02	2026-01-11 15:36:49.008804+02	f	1	3	3	10
25	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 96, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 257.28, "reporting_year": 2021, "reporting_month": "February"}	2026-01-11 15:36:49.012872+02	2026-01-11 15:36:49.012887+02	f	1	3	3	10
26	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 109, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 292.12, "reporting_year": 2021, "reporting_month": "March"}	2026-01-11 15:36:49.016809+02	2026-01-11 15:36:49.016825+02	f	1	3	3	10
27	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 113, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 302.84, "reporting_year": 2021, "reporting_month": "April"}	2026-01-11 15:36:49.024776+02	2026-01-11 15:36:49.024792+02	f	1	3	3	10
28	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 146, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 391.28, "reporting_year": 2021, "reporting_month": "May"}	2026-01-11 15:36:49.028541+02	2026-01-11 15:36:49.028556+02	f	1	3	3	10
29	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 166, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 444.88, "reporting_year": 2021, "reporting_month": "June"}	2026-01-11 15:36:49.032445+02	2026-01-11 15:36:49.032461+02	f	1	3	3	10
30	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 191, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 511.88, "reporting_year": 2021, "reporting_month": "July"}	2026-01-11 15:36:49.037975+02	2026-01-11 15:36:49.038008+02	f	1	3	3	10
31	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 199, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 533.32, "reporting_year": 2021, "reporting_month": "August"}	2026-01-11 15:36:49.043915+02	2026-01-11 15:36:49.043933+02	f	1	3	3	10
32	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 183, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 490.44, "reporting_year": 2021, "reporting_month": "September"}	2026-01-11 15:36:49.048029+02	2026-01-11 15:36:49.048048+02	f	1	3	3	10
33	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 148, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 396.64, "reporting_year": 2021, "reporting_month": "October"}	2026-01-11 15:36:49.052596+02	2026-01-11 15:36:49.052619+02	f	1	3	3	10
34	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 128, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 343.04, "reporting_year": 2021, "reporting_month": "November"}	2026-01-11 15:36:49.057474+02	2026-01-11 15:36:49.057499+02	f	1	3	3	10
35	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 100, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 268.0, "reporting_year": 2021, "reporting_month": "December"}	2026-01-11 15:36:49.062993+02	2026-01-11 15:36:49.063017+02	f	1	3	3	10
36	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 96, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 257.28, "reporting_year": 2022, "reporting_month": "January"}	2026-01-11 15:36:49.067551+02	2026-01-11 15:36:49.067573+02	f	1	3	3	10
37	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 85, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 227.8, "reporting_year": 2022, "reporting_month": "February"}	2026-01-11 15:36:49.074109+02	2026-01-11 15:36:49.074125+02	f	1	3	3	10
38	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 103, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 276.04, "reporting_year": 2022, "reporting_month": "March"}	2026-01-11 15:36:49.077781+02	2026-01-11 15:36:49.077794+02	f	1	3	3	10
39	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 132, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 353.76, "reporting_year": 2022, "reporting_month": "April"}	2026-01-11 15:36:49.081235+02	2026-01-11 15:36:49.08125+02	f	1	3	3	10
40	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 148, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 396.64, "reporting_year": 2022, "reporting_month": "May"}	2026-01-11 15:36:49.086253+02	2026-01-11 15:36:49.08627+02	f	1	3	3	10
41	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 164, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 439.52, "reporting_year": 2022, "reporting_month": "June"}	2026-01-11 15:36:49.090139+02	2026-01-11 15:36:49.090155+02	f	1	3	3	10
42	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 179, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 479.72, "reporting_year": 2022, "reporting_month": "July"}	2026-01-11 15:36:49.094317+02	2026-01-11 15:36:49.094332+02	f	1	3	3	10
43	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 190, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 509.2, "reporting_year": 2022, "reporting_month": "August"}	2026-01-11 15:36:49.097776+02	2026-01-11 15:36:49.09779+02	f	1	3	3	10
44	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 160, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 428.8, "reporting_year": 2022, "reporting_month": "September"}	2026-01-11 15:36:49.101683+02	2026-01-11 15:36:49.101698+02	f	1	3	3	10
45	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 141, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 377.88, "reporting_year": 2022, "reporting_month": "October"}	2026-01-11 15:36:49.106465+02	2026-01-11 15:36:49.106479+02	f	1	3	3	10
46	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 110, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 294.8, "reporting_year": 2022, "reporting_month": "November"}	2026-01-11 15:36:49.110468+02	2026-01-11 15:36:49.110484+02	f	1	3	3	10
47	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 104, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 278.72, "reporting_year": 2022, "reporting_month": "December"}	2026-01-11 15:36:49.114695+02	2026-01-11 15:36:49.114718+02	f	1	3	3	10
48	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 105, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 281.4, "reporting_year": 2023, "reporting_month": "January"}	2026-01-11 15:36:49.118918+02	2026-01-11 15:36:49.118934+02	f	1	3	3	10
49	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 96, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 257.28, "reporting_year": 2023, "reporting_month": "February"}	2026-01-11 15:36:49.123733+02	2026-01-11 15:36:49.123748+02	f	1	3	3	10
50	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 113, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 302.84, "reporting_year": 2023, "reporting_month": "March"}	2026-01-11 15:36:49.127177+02	2026-01-11 15:36:49.127191+02	f	1	3	3	10
51	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 116, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 310.88, "reporting_year": 2023, "reporting_month": "April"}	2026-01-11 15:36:49.131215+02	2026-01-11 15:36:49.131239+02	f	1	3	3	10
52	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 159, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 426.12, "reporting_year": 2023, "reporting_month": "May"}	2026-01-11 15:36:49.135226+02	2026-01-11 15:36:49.135242+02	f	1	3	3	10
53	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 167, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 447.56, "reporting_year": 2023, "reporting_month": "June"}	2026-01-11 15:36:49.140204+02	2026-01-11 15:36:49.140219+02	f	1	3	3	10
54	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 203, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 544.04, "reporting_year": 2023, "reporting_month": "July"}	2026-01-11 15:36:49.144107+02	2026-01-11 15:36:49.144124+02	f	1	3	3	10
55	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 181, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 485.08, "reporting_year": 2023, "reporting_month": "August"}	2026-01-11 15:36:49.150598+02	2026-01-11 15:36:49.150613+02	f	1	3	3	10
56	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 178, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 477.04, "reporting_year": 2023, "reporting_month": "September"}	2026-01-11 15:36:49.154587+02	2026-01-11 15:36:49.154603+02	f	1	3	3	10
57	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 144, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 385.92, "reporting_year": 2023, "reporting_month": "October"}	2026-01-11 15:36:49.158593+02	2026-01-11 15:36:49.158609+02	f	1	3	3	10
58	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 116, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 310.88, "reporting_year": 2023, "reporting_month": "November"}	2026-01-11 15:36:49.163614+02	2026-01-11 15:36:49.163631+02	f	1	3	3	10
59	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 105, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 281.4, "reporting_year": 2023, "reporting_month": "December"}	2026-01-11 15:36:49.167559+02	2026-01-11 15:36:49.167574+02	f	1	3	3	10
60	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 94, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 251.92, "reporting_year": 2024, "reporting_month": "January"}	2026-01-11 15:36:49.171199+02	2026-01-11 15:36:49.171214+02	f	1	3	3	10
61	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 88, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 235.84, "reporting_year": 2024, "reporting_month": "February"}	2026-01-11 15:36:49.175002+02	2026-01-11 15:36:49.175017+02	f	1	3	3	10
62	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 114, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 305.52, "reporting_year": 2024, "reporting_month": "March"}	2026-01-11 15:36:49.178996+02	2026-01-11 15:36:49.179012+02	f	1	3	3	10
63	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 107, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 286.76, "reporting_year": 2024, "reporting_month": "April"}	2026-01-11 15:36:49.183985+02	2026-01-11 15:36:49.184001+02	f	1	3	3	10
64	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 165, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 442.2, "reporting_year": 2024, "reporting_month": "May"}	2026-01-11 15:36:49.187604+02	2026-01-11 15:36:49.18762+02	f	1	3	3	10
65	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 171, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 458.28, "reporting_year": 2024, "reporting_month": "June"}	2026-01-11 15:36:49.191272+02	2026-01-11 15:36:49.191288+02	f	1	3	3	10
66	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 178, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 477.04, "reporting_year": 2024, "reporting_month": "July"}	2026-01-11 15:36:49.195317+02	2026-01-11 15:36:49.195333+02	f	1	3	3	10
67	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 164, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 439.52, "reporting_year": 2024, "reporting_month": "August"}	2026-01-11 15:36:49.199245+02	2026-01-11 15:36:49.199261+02	f	1	3	3	10
68	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 146, "fuel_type": "Diesel", "equipment_id": "GEN-SV-03", "co2e_emissions": 391.28, "reporting_year": 2024, "reporting_month": "September"}	2026-01-11 15:36:49.203134+02	2026-01-11 15:36:49.203149+02	f	1	3	3	10
69	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 120, "fuel_type": "Diesel", "equipment_id": "GEN-SV-01", "co2e_emissions": 321.6, "reporting_year": 2024, "reporting_month": "October"}	2026-01-11 15:36:49.206461+02	2026-01-11 15:36:49.206476+02	f	1	3	3	10
70	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 111, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 297.48, "reporting_year": 2024, "reporting_month": "November"}	2026-01-11 15:36:49.211648+02	2026-01-11 15:36:49.211666+02	f	1	3	3	10
71	{"unit": "Liters", "notes": "", "campus": "Smart Village", "quantity": 98, "fuel_type": "Diesel", "equipment_id": "GEN-SV-02", "co2e_emissions": 262.64, "reporting_year": 2024, "reporting_month": "December"}	2026-01-11 15:36:49.218099+02	2026-01-11 15:36:49.218115+02	f	1	3	3	10
72	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 162, "fuel_type": "LPG", "co2e_emissions": 244.62, "reporting_year": 2020, "reporting_month": "January"}	2026-01-11 15:36:49.22373+02	2026-01-11 15:36:49.223747+02	f	1	3	3	12
73	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 180, "fuel_type": "LPG", "co2e_emissions": 271.8, "reporting_year": 2020, "reporting_month": "February"}	2026-01-11 15:36:49.227827+02	2026-01-11 15:36:49.227844+02	f	1	3	3	12
74	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 185, "fuel_type": "LPG", "co2e_emissions": 279.35, "reporting_year": 2020, "reporting_month": "March"}	2026-01-11 15:36:49.23153+02	2026-01-11 15:36:49.231544+02	f	1	3	3	12
75	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 186, "fuel_type": "LPG", "co2e_emissions": 280.86, "reporting_year": 2020, "reporting_month": "April"}	2026-01-11 15:36:49.236357+02	2026-01-11 15:36:49.236373+02	f	1	3	3	12
76	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 186, "fuel_type": "LPG", "co2e_emissions": 280.86, "reporting_year": 2020, "reporting_month": "May"}	2026-01-11 15:36:49.240413+02	2026-01-11 15:36:49.240432+02	f	1	3	3	12
77	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 144, "fuel_type": "LPG", "co2e_emissions": 217.44, "reporting_year": 2020, "reporting_month": "June"}	2026-01-11 15:36:49.244752+02	2026-01-11 15:36:49.244767+02	f	1	3	3	12
78	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 79, "fuel_type": "LPG", "co2e_emissions": 119.29, "reporting_year": 2020, "reporting_month": "July"}	2026-01-11 15:36:49.248535+02	2026-01-11 15:36:49.248554+02	f	1	3	3	12
79	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 56, "fuel_type": "LPG", "co2e_emissions": 84.56, "reporting_year": 2020, "reporting_month": "August"}	2026-01-11 15:36:49.252293+02	2026-01-11 15:36:49.252309+02	f	1	3	3	12
80	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 189, "fuel_type": "LPG", "co2e_emissions": 285.39, "reporting_year": 2020, "reporting_month": "September"}	2026-01-11 15:36:49.257807+02	2026-01-11 15:36:49.257824+02	f	1	3	3	12
81	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 182, "fuel_type": "LPG", "co2e_emissions": 274.82, "reporting_year": 2020, "reporting_month": "October"}	2026-01-11 15:36:49.26684+02	2026-01-11 15:36:49.266856+02	f	1	3	3	12
82	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 188, "fuel_type": "LPG", "co2e_emissions": 283.88, "reporting_year": 2020, "reporting_month": "November"}	2026-01-11 15:36:49.270893+02	2026-01-11 15:36:49.270923+02	f	1	3	3	12
83	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 170, "fuel_type": "LPG", "co2e_emissions": 256.7, "reporting_year": 2020, "reporting_month": "December"}	2026-01-11 15:36:49.275057+02	2026-01-11 15:36:49.275085+02	f	1	3	3	12
84	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 185, "fuel_type": "LPG", "co2e_emissions": 279.35, "reporting_year": 2021, "reporting_month": "January"}	2026-01-11 15:36:49.280532+02	2026-01-11 15:36:49.280548+02	f	1	3	3	12
85	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 190, "fuel_type": "LPG", "co2e_emissions": 286.9, "reporting_year": 2021, "reporting_month": "February"}	2026-01-11 15:36:49.286381+02	2026-01-11 15:36:49.2864+02	f	1	3	3	12
86	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 213, "fuel_type": "LPG", "co2e_emissions": 321.63, "reporting_year": 2021, "reporting_month": "March"}	2026-01-11 15:36:49.290544+02	2026-01-11 15:36:49.290561+02	f	1	3	3	12
87	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 196, "fuel_type": "LPG", "co2e_emissions": 295.96, "reporting_year": 2021, "reporting_month": "April"}	2026-01-11 15:36:49.294249+02	2026-01-11 15:36:49.294265+02	f	1	3	3	12
88	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 176, "fuel_type": "LPG", "co2e_emissions": 265.76, "reporting_year": 2021, "reporting_month": "May"}	2026-01-11 15:36:49.298433+02	2026-01-11 15:36:49.298458+02	f	1	3	3	12
89	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 131, "fuel_type": "LPG", "co2e_emissions": 197.81, "reporting_year": 2021, "reporting_month": "June"}	2026-01-11 15:36:49.303843+02	2026-01-11 15:36:49.303861+02	f	1	3	3	12
90	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 76, "fuel_type": "LPG", "co2e_emissions": 114.76, "reporting_year": 2021, "reporting_month": "July"}	2026-01-11 15:36:49.313051+02	2026-01-11 15:36:49.313068+02	f	1	3	3	12
91	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 64, "fuel_type": "LPG", "co2e_emissions": 96.64, "reporting_year": 2021, "reporting_month": "August"}	2026-01-11 15:36:49.3169+02	2026-01-11 15:36:49.316916+02	f	1	3	3	12
92	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 199, "fuel_type": "LPG", "co2e_emissions": 300.49, "reporting_year": 2021, "reporting_month": "September"}	2026-01-11 15:36:49.32097+02	2026-01-11 15:36:49.320986+02	f	1	3	3	12
93	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 202, "fuel_type": "LPG", "co2e_emissions": 305.02, "reporting_year": 2021, "reporting_month": "October"}	2026-01-11 15:36:49.327452+02	2026-01-11 15:36:49.327469+02	f	1	3	3	12
94	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 214, "fuel_type": "LPG", "co2e_emissions": 323.14, "reporting_year": 2021, "reporting_month": "November"}	2026-01-11 15:36:49.332307+02	2026-01-11 15:36:49.332323+02	f	1	3	3	12
95	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 172, "fuel_type": "LPG", "co2e_emissions": 259.72, "reporting_year": 2021, "reporting_month": "December"}	2026-01-11 15:36:49.336686+02	2026-01-11 15:36:49.336702+02	f	1	3	3	12
96	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 186, "fuel_type": "LPG", "co2e_emissions": 280.86, "reporting_year": 2022, "reporting_month": "January"}	2026-01-11 15:36:49.341681+02	2026-01-11 15:36:49.341696+02	f	1	3	3	12
97	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 212, "fuel_type": "LPG", "co2e_emissions": 320.12, "reporting_year": 2022, "reporting_month": "February"}	2026-01-11 15:36:49.345681+02	2026-01-11 15:36:49.345697+02	f	1	3	3	12
98	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 228, "fuel_type": "LPG", "co2e_emissions": 344.28, "reporting_year": 2022, "reporting_month": "March"}	2026-01-11 15:36:49.351032+02	2026-01-11 15:36:49.351051+02	f	1	3	3	12
99	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 214, "fuel_type": "LPG", "co2e_emissions": 323.14, "reporting_year": 2022, "reporting_month": "April"}	2026-01-11 15:36:49.357185+02	2026-01-11 15:36:49.357212+02	f	1	3	3	12
100	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 188, "fuel_type": "LPG", "co2e_emissions": 283.88, "reporting_year": 2022, "reporting_month": "May"}	2026-01-11 15:36:49.364857+02	2026-01-11 15:36:49.36488+02	f	1	3	3	12
101	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 156, "fuel_type": "LPG", "co2e_emissions": 235.56, "reporting_year": 2022, "reporting_month": "June"}	2026-01-11 15:36:49.370776+02	2026-01-11 15:36:49.370816+02	f	1	3	3	12
102	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 90, "fuel_type": "LPG", "co2e_emissions": 135.9, "reporting_year": 2022, "reporting_month": "July"}	2026-01-11 15:36:49.377652+02	2026-01-11 15:36:49.377668+02	f	1	3	3	12
103	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 60, "fuel_type": "LPG", "co2e_emissions": 90.6, "reporting_year": 2022, "reporting_month": "August"}	2026-01-11 15:36:49.383668+02	2026-01-11 15:36:49.383684+02	f	1	3	3	12
104	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 204, "fuel_type": "LPG", "co2e_emissions": 308.04, "reporting_year": 2022, "reporting_month": "September"}	2026-01-11 15:36:49.387633+02	2026-01-11 15:36:49.387649+02	f	1	3	3	12
105	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 211, "fuel_type": "LPG", "co2e_emissions": 318.61, "reporting_year": 2022, "reporting_month": "October"}	2026-01-11 15:36:49.39182+02	2026-01-11 15:36:49.391845+02	f	1	3	3	12
106	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 205, "fuel_type": "LPG", "co2e_emissions": 309.55, "reporting_year": 2022, "reporting_month": "November"}	2026-01-11 15:36:49.397181+02	2026-01-11 15:36:49.397202+02	f	1	3	3	12
107	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 183, "fuel_type": "LPG", "co2e_emissions": 276.33, "reporting_year": 2022, "reporting_month": "December"}	2026-01-11 15:36:49.404651+02	2026-01-11 15:36:49.404666+02	f	1	3	3	12
108	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 186, "fuel_type": "LPG", "co2e_emissions": 280.86, "reporting_year": 2023, "reporting_month": "January"}	2026-01-11 15:36:49.408514+02	2026-01-11 15:36:49.408528+02	f	1	3	3	12
109	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 226, "fuel_type": "LPG", "co2e_emissions": 341.26, "reporting_year": 2023, "reporting_month": "February"}	2026-01-11 15:36:49.412649+02	2026-01-11 15:36:49.412666+02	f	1	3	3	12
110	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 194, "fuel_type": "LPG", "co2e_emissions": 292.94, "reporting_year": 2023, "reporting_month": "March"}	2026-01-11 15:36:49.41736+02	2026-01-11 15:36:49.417376+02	f	1	3	3	12
111	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 218, "fuel_type": "LPG", "co2e_emissions": 329.18, "reporting_year": 2023, "reporting_month": "April"}	2026-01-11 15:36:49.424922+02	2026-01-11 15:36:49.424939+02	f	1	3	3	12
112	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 203, "fuel_type": "LPG", "co2e_emissions": 306.53, "reporting_year": 2023, "reporting_month": "May"}	2026-01-11 15:36:49.433469+02	2026-01-11 15:36:49.433488+02	f	1	3	3	12
113	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 135, "fuel_type": "LPG", "co2e_emissions": 203.85, "reporting_year": 2023, "reporting_month": "June"}	2026-01-11 15:36:49.43948+02	2026-01-11 15:36:49.439496+02	f	1	3	3	12
114	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 82, "fuel_type": "LPG", "co2e_emissions": 123.82, "reporting_year": 2023, "reporting_month": "July"}	2026-01-11 15:36:49.44522+02	2026-01-11 15:36:49.445236+02	f	1	3	3	12
115	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 60, "fuel_type": "LPG", "co2e_emissions": 90.6, "reporting_year": 2023, "reporting_month": "August"}	2026-01-11 15:36:49.449271+02	2026-01-11 15:36:49.449288+02	f	1	3	3	12
116	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 212, "fuel_type": "LPG", "co2e_emissions": 320.12, "reporting_year": 2023, "reporting_month": "September"}	2026-01-11 15:36:49.453319+02	2026-01-11 15:36:49.453337+02	f	1	3	3	12
117	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 198, "fuel_type": "LPG", "co2e_emissions": 298.98, "reporting_year": 2023, "reporting_month": "October"}	2026-01-11 15:36:49.458151+02	2026-01-11 15:36:49.458177+02	f	1	3	3	12
118	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 212, "fuel_type": "LPG", "co2e_emissions": 320.12, "reporting_year": 2023, "reporting_month": "November"}	2026-01-11 15:36:49.463699+02	2026-01-11 15:36:49.46373+02	f	1	3	3	12
119	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 188, "fuel_type": "LPG", "co2e_emissions": 283.88, "reporting_year": 2023, "reporting_month": "December"}	2026-01-11 15:36:49.468243+02	2026-01-11 15:36:49.468267+02	f	1	3	3	12
120	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 202, "fuel_type": "LPG", "co2e_emissions": 305.02, "reporting_year": 2024, "reporting_month": "January"}	2026-01-11 15:36:49.473499+02	2026-01-11 15:36:49.473516+02	f	1	3	3	12
121	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 219, "fuel_type": "LPG", "co2e_emissions": 330.69, "reporting_year": 2024, "reporting_month": "February"}	2026-01-11 15:36:49.477648+02	2026-01-11 15:36:49.477665+02	f	1	3	3	12
122	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 211, "fuel_type": "LPG", "co2e_emissions": 318.61, "reporting_year": 2024, "reporting_month": "March"}	2026-01-11 15:36:49.484137+02	2026-01-11 15:36:49.484152+02	f	1	3	3	12
123	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 197, "fuel_type": "LPG", "co2e_emissions": 297.47, "reporting_year": 2024, "reporting_month": "April"}	2026-01-11 15:36:49.48894+02	2026-01-11 15:36:49.488951+02	f	1	3	3	12
124	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 203, "fuel_type": "LPG", "co2e_emissions": 306.53, "reporting_year": 2024, "reporting_month": "May"}	2026-01-11 15:36:49.492847+02	2026-01-11 15:36:49.492862+02	f	1	3	3	12
125	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 162, "fuel_type": "LPG", "co2e_emissions": 244.62, "reporting_year": 2024, "reporting_month": "June"}	2026-01-11 15:36:49.496462+02	2026-01-11 15:36:49.496476+02	f	1	3	3	12
126	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 92, "fuel_type": "LPG", "co2e_emissions": 138.92, "reporting_year": 2024, "reporting_month": "July"}	2026-01-11 15:36:49.499903+02	2026-01-11 15:36:49.499915+02	f	1	3	3	12
127	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 60, "fuel_type": "LPG", "co2e_emissions": 90.6, "reporting_year": 2024, "reporting_month": "August"}	2026-01-11 15:36:49.503469+02	2026-01-11 15:36:49.503482+02	f	1	3	3	12
128	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 211, "fuel_type": "LPG", "co2e_emissions": 318.61, "reporting_year": 2024, "reporting_month": "September"}	2026-01-11 15:36:49.508476+02	2026-01-11 15:36:49.508491+02	f	1	3	3	12
129	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 202, "fuel_type": "LPG", "co2e_emissions": 305.02, "reporting_year": 2024, "reporting_month": "October"}	2026-01-11 15:36:49.512458+02	2026-01-11 15:36:49.512472+02	f	1	3	3	12
130	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 223, "fuel_type": "LPG", "co2e_emissions": 336.73, "reporting_year": 2024, "reporting_month": "November"}	2026-01-11 15:36:49.51597+02	2026-01-11 15:36:49.515981+02	f	1	3	3	12
131	{"unit": "kg", "notes": "Campus canteen operations", "campus": "Smart Village", "quantity": 170, "fuel_type": "LPG", "co2e_emissions": 256.7, "reporting_year": 2024, "reporting_month": "December"}	2026-01-11 15:36:49.519123+02	2026-01-11 15:36:49.519135+02	f	1	3	3	12
132	{"fuel_type": "Diesel", "distance_km": 5904, "vehicle_type": "Staff Bus", "co2e_emissions": 1977.84, "reporting_year": 2020, "quantity_liters": 738, "reporting_month": "January"}	2026-01-11 15:36:49.574268+02	2026-01-11 15:36:49.574284+02	f	1	3	3	13
133	{"fuel_type": "Diesel", "distance_km": 5368, "vehicle_type": "Staff Bus", "co2e_emissions": 1798.28, "reporting_year": 2020, "quantity_liters": 671, "reporting_month": "January"}	2026-01-11 15:36:49.578007+02	2026-01-11 15:36:49.578021+02	f	1	3	3	13
134	{"fuel_type": "Gasoline", "distance_km": 1140, "vehicle_type": "Administrative Car", "co2e_emissions": 263.34, "reporting_year": 2020, "quantity_liters": 114, "reporting_month": "January"}	2026-01-11 15:36:49.582541+02	2026-01-11 15:36:49.582555+02	f	1	3	3	13
135	{"fuel_type": "Gasoline", "distance_km": 890, "vehicle_type": "Administrative Car", "co2e_emissions": 205.59, "reporting_year": 2020, "quantity_liters": 89, "reporting_month": "January"}	2026-01-11 15:36:49.586235+02	2026-01-11 15:36:49.58625+02	f	1	3	3	13
136	{"fuel_type": "Diesel", "distance_km": 1328, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 444.88, "reporting_year": 2020, "quantity_liters": 166, "reporting_month": "January"}	2026-01-11 15:36:49.589951+02	2026-01-11 15:36:49.589965+02	f	1	3	3	13
137	{"fuel_type": "Gasoline", "distance_km": 800, "vehicle_type": "Security Patrol", "co2e_emissions": 184.8, "reporting_year": 2020, "quantity_liters": 80, "reporting_month": "January"}	2026-01-11 15:36:49.594666+02	2026-01-11 15:36:49.594678+02	f	1	3	3	13
138	{"fuel_type": "Diesel", "distance_km": 5832, "vehicle_type": "Staff Bus", "co2e_emissions": 1953.72, "reporting_year": 2020, "quantity_liters": 729, "reporting_month": "February"}	2026-01-11 15:36:49.598213+02	2026-01-11 15:36:49.598227+02	f	1	3	3	13
139	{"fuel_type": "Diesel", "distance_km": 5528, "vehicle_type": "Staff Bus", "co2e_emissions": 1851.88, "reporting_year": 2020, "quantity_liters": 691, "reporting_month": "February"}	2026-01-11 15:36:49.603011+02	2026-01-11 15:36:49.603027+02	f	1	3	3	13
140	{"fuel_type": "Gasoline", "distance_km": 1290, "vehicle_type": "Administrative Car", "co2e_emissions": 297.99, "reporting_year": 2020, "quantity_liters": 129, "reporting_month": "February"}	2026-01-11 15:36:49.606816+02	2026-01-11 15:36:49.606829+02	f	1	3	3	13
141	{"fuel_type": "Gasoline", "distance_km": 1010, "vehicle_type": "Administrative Car", "co2e_emissions": 233.31, "reporting_year": 2020, "quantity_liters": 101, "reporting_month": "February"}	2026-01-11 15:36:49.610659+02	2026-01-11 15:36:49.610673+02	f	1	3	3	13
142	{"fuel_type": "Diesel", "distance_km": 1344, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 450.24, "reporting_year": 2020, "quantity_liters": 168, "reporting_month": "February"}	2026-01-11 15:36:49.615594+02	2026-01-11 15:36:49.61561+02	f	1	3	3	13
143	{"fuel_type": "Gasoline", "distance_km": 920, "vehicle_type": "Security Patrol", "co2e_emissions": 212.52, "reporting_year": 2020, "quantity_liters": 92, "reporting_month": "February"}	2026-01-11 15:36:49.619484+02	2026-01-11 15:36:49.619499+02	f	1	3	3	13
144	{"fuel_type": "Diesel", "distance_km": 6168, "vehicle_type": "Staff Bus", "co2e_emissions": 2066.28, "reporting_year": 2020, "quantity_liters": 771, "reporting_month": "March"}	2026-01-11 15:36:49.623135+02	2026-01-11 15:36:49.623149+02	f	1	3	3	13
145	{"fuel_type": "Diesel", "distance_km": 5648, "vehicle_type": "Staff Bus", "co2e_emissions": 1892.08, "reporting_year": 2020, "quantity_liters": 706, "reporting_month": "March"}	2026-01-11 15:36:49.626828+02	2026-01-11 15:36:49.626841+02	f	1	3	3	13
146	{"fuel_type": "Gasoline", "distance_km": 1180, "vehicle_type": "Administrative Car", "co2e_emissions": 272.58, "reporting_year": 2020, "quantity_liters": 118, "reporting_month": "March"}	2026-01-11 15:36:49.630504+02	2026-01-11 15:36:49.630516+02	f	1	3	3	13
147	{"fuel_type": "Gasoline", "distance_km": 900, "vehicle_type": "Administrative Car", "co2e_emissions": 207.9, "reporting_year": 2020, "quantity_liters": 90, "reporting_month": "March"}	2026-01-11 15:36:49.635926+02	2026-01-11 15:36:49.635941+02	f	1	3	3	13
148	{"fuel_type": "Diesel", "distance_km": 1504, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 503.84, "reporting_year": 2020, "quantity_liters": 188, "reporting_month": "March"}	2026-01-11 15:36:49.640163+02	2026-01-11 15:36:49.640178+02	f	1	3	3	13
149	{"fuel_type": "Gasoline", "distance_km": 910, "vehicle_type": "Security Patrol", "co2e_emissions": 210.21, "reporting_year": 2020, "quantity_liters": 91, "reporting_month": "March"}	2026-01-11 15:36:49.643816+02	2026-01-11 15:36:49.643829+02	f	1	3	3	13
150	{"fuel_type": "Diesel", "distance_km": 6920, "vehicle_type": "Staff Bus", "co2e_emissions": 2318.2, "reporting_year": 2020, "quantity_liters": 865, "reporting_month": "April"}	2026-01-11 15:36:49.647657+02	2026-01-11 15:36:49.647675+02	f	1	3	3	13
151	{"fuel_type": "Diesel", "distance_km": 5520, "vehicle_type": "Staff Bus", "co2e_emissions": 1849.2, "reporting_year": 2020, "quantity_liters": 690, "reporting_month": "April"}	2026-01-11 15:36:49.651953+02	2026-01-11 15:36:49.651968+02	f	1	3	3	13
152	{"fuel_type": "Gasoline", "distance_km": 1140, "vehicle_type": "Administrative Car", "co2e_emissions": 263.34, "reporting_year": 2020, "quantity_liters": 114, "reporting_month": "April"}	2026-01-11 15:36:49.658723+02	2026-01-11 15:36:49.658738+02	f	1	3	3	13
153	{"fuel_type": "Gasoline", "distance_km": 1050, "vehicle_type": "Administrative Car", "co2e_emissions": 242.55, "reporting_year": 2020, "quantity_liters": 105, "reporting_month": "April"}	2026-01-11 15:36:49.662732+02	2026-01-11 15:36:49.66275+02	f	1	3	3	13
154	{"fuel_type": "Diesel", "distance_km": 1520, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 509.2, "reporting_year": 2020, "quantity_liters": 190, "reporting_month": "April"}	2026-01-11 15:36:49.667635+02	2026-01-11 15:36:49.667651+02	f	1	3	3	13
155	{"fuel_type": "Gasoline", "distance_km": 880, "vehicle_type": "Security Patrol", "co2e_emissions": 203.28, "reporting_year": 2020, "quantity_liters": 88, "reporting_month": "April"}	2026-01-11 15:36:49.671107+02	2026-01-11 15:36:49.67112+02	f	1	3	3	13
156	{"fuel_type": "Diesel", "distance_km": 6048, "vehicle_type": "Staff Bus", "co2e_emissions": 2026.08, "reporting_year": 2020, "quantity_liters": 756, "reporting_month": "May"}	2026-01-11 15:36:49.674296+02	2026-01-11 15:36:49.674309+02	f	1	3	3	13
157	{"fuel_type": "Diesel", "distance_km": 5000, "vehicle_type": "Staff Bus", "co2e_emissions": 1675.0, "reporting_year": 2020, "quantity_liters": 625, "reporting_month": "May"}	2026-01-11 15:36:49.677775+02	2026-01-11 15:36:49.677789+02	f	1	3	3	13
158	{"fuel_type": "Gasoline", "distance_km": 1140, "vehicle_type": "Administrative Car", "co2e_emissions": 263.34, "reporting_year": 2020, "quantity_liters": 114, "reporting_month": "May"}	2026-01-11 15:36:49.68309+02	2026-01-11 15:36:49.683106+02	f	1	3	3	13
159	{"fuel_type": "Gasoline", "distance_km": 970, "vehicle_type": "Administrative Car", "co2e_emissions": 224.07, "reporting_year": 2020, "quantity_liters": 97, "reporting_month": "May"}	2026-01-11 15:36:49.686989+02	2026-01-11 15:36:49.687003+02	f	1	3	3	13
160	{"fuel_type": "Diesel", "distance_km": 1168, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 391.28, "reporting_year": 2020, "quantity_liters": 146, "reporting_month": "May"}	2026-01-11 15:36:49.690588+02	2026-01-11 15:36:49.690601+02	f	1	3	3	13
161	{"fuel_type": "Gasoline", "distance_km": 730, "vehicle_type": "Security Patrol", "co2e_emissions": 168.63, "reporting_year": 2020, "quantity_liters": 73, "reporting_month": "May"}	2026-01-11 15:36:49.694404+02	2026-01-11 15:36:49.694419+02	f	1	3	3	13
162	{"fuel_type": "Diesel", "distance_km": 4536, "vehicle_type": "Staff Bus", "co2e_emissions": 1519.56, "reporting_year": 2020, "quantity_liters": 567, "reporting_month": "June"}	2026-01-11 15:36:49.698448+02	2026-01-11 15:36:49.698463+02	f	1	3	3	13
163	{"fuel_type": "Diesel", "distance_km": 3968, "vehicle_type": "Staff Bus", "co2e_emissions": 1329.28, "reporting_year": 2020, "quantity_liters": 496, "reporting_month": "June"}	2026-01-11 15:36:49.702568+02	2026-01-11 15:36:49.702582+02	f	1	3	3	13
164	{"fuel_type": "Gasoline", "distance_km": 880, "vehicle_type": "Administrative Car", "co2e_emissions": 203.28, "reporting_year": 2020, "quantity_liters": 88, "reporting_month": "June"}	2026-01-11 15:36:49.706286+02	2026-01-11 15:36:49.706299+02	f	1	3	3	13
165	{"fuel_type": "Gasoline", "distance_km": 700, "vehicle_type": "Administrative Car", "co2e_emissions": 161.7, "reporting_year": 2020, "quantity_liters": 70, "reporting_month": "June"}	2026-01-11 15:36:49.710039+02	2026-01-11 15:36:49.710055+02	f	1	3	3	13
166	{"fuel_type": "Diesel", "distance_km": 912, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 305.52, "reporting_year": 2020, "quantity_liters": 114, "reporting_month": "June"}	2026-01-11 15:36:49.714172+02	2026-01-11 15:36:49.714188+02	f	1	3	3	13
167	{"fuel_type": "Gasoline", "distance_km": 580, "vehicle_type": "Security Patrol", "co2e_emissions": 133.98, "reporting_year": 2020, "quantity_liters": 58, "reporting_month": "June"}	2026-01-11 15:36:49.717913+02	2026-01-11 15:36:49.717926+02	f	1	3	3	13
168	{"fuel_type": "Diesel", "distance_km": 2328, "vehicle_type": "Staff Bus", "co2e_emissions": 779.88, "reporting_year": 2020, "quantity_liters": 291, "reporting_month": "July"}	2026-01-11 15:36:49.721851+02	2026-01-11 15:36:49.721863+02	f	1	3	3	13
169	{"fuel_type": "Diesel", "distance_km": 2520, "vehicle_type": "Staff Bus", "co2e_emissions": 844.2, "reporting_year": 2020, "quantity_liters": 315, "reporting_month": "July"}	2026-01-11 15:36:49.727413+02	2026-01-11 15:36:49.727429+02	f	1	3	3	13
170	{"fuel_type": "Gasoline", "distance_km": 450, "vehicle_type": "Administrative Car", "co2e_emissions": 103.95, "reporting_year": 2020, "quantity_liters": 45, "reporting_month": "July"}	2026-01-11 15:36:49.731518+02	2026-01-11 15:36:49.731531+02	f	1	3	3	13
171	{"fuel_type": "Gasoline", "distance_km": 360, "vehicle_type": "Administrative Car", "co2e_emissions": 83.16, "reporting_year": 2020, "quantity_liters": 36, "reporting_month": "July"}	2026-01-11 15:36:49.735281+02	2026-01-11 15:36:49.735295+02	f	1	3	3	13
172	{"fuel_type": "Diesel", "distance_km": 600, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 201.0, "reporting_year": 2020, "quantity_liters": 75, "reporting_month": "July"}	2026-01-11 15:36:49.739078+02	2026-01-11 15:36:49.739091+02	f	1	3	3	13
173	{"fuel_type": "Gasoline", "distance_km": 340, "vehicle_type": "Security Patrol", "co2e_emissions": 78.54, "reporting_year": 2020, "quantity_liters": 34, "reporting_month": "July"}	2026-01-11 15:36:49.74378+02	2026-01-11 15:36:49.743796+02	f	1	3	3	13
174	{"fuel_type": "Diesel", "distance_km": 2016, "vehicle_type": "Staff Bus", "co2e_emissions": 675.36, "reporting_year": 2020, "quantity_liters": 252, "reporting_month": "August"}	2026-01-11 15:36:49.749162+02	2026-01-11 15:36:49.749178+02	f	1	3	3	13
175	{"fuel_type": "Diesel", "distance_km": 1784, "vehicle_type": "Staff Bus", "co2e_emissions": 597.64, "reporting_year": 2020, "quantity_liters": 223, "reporting_month": "August"}	2026-01-11 15:36:49.753714+02	2026-01-11 15:36:49.753726+02	f	1	3	3	13
176	{"fuel_type": "Gasoline", "distance_km": 330, "vehicle_type": "Administrative Car", "co2e_emissions": 76.23, "reporting_year": 2020, "quantity_liters": 33, "reporting_month": "August"}	2026-01-11 15:36:49.758742+02	2026-01-11 15:36:49.758759+02	f	1	3	3	13
177	{"fuel_type": "Gasoline", "distance_km": 320, "vehicle_type": "Administrative Car", "co2e_emissions": 73.92, "reporting_year": 2020, "quantity_liters": 32, "reporting_month": "August"}	2026-01-11 15:36:49.76244+02	2026-01-11 15:36:49.762454+02	f	1	3	3	13
178	{"fuel_type": "Diesel", "distance_km": 392, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 131.32, "reporting_year": 2020, "quantity_liters": 49, "reporting_month": "August"}	2026-01-11 15:36:49.76595+02	2026-01-11 15:36:49.765961+02	f	1	3	3	13
179	{"fuel_type": "Gasoline", "distance_km": 280, "vehicle_type": "Security Patrol", "co2e_emissions": 64.68, "reporting_year": 2020, "quantity_liters": 28, "reporting_month": "August"}	2026-01-11 15:36:49.769346+02	2026-01-11 15:36:49.769358+02	f	1	3	3	13
180	{"fuel_type": "Diesel", "distance_km": 5880, "vehicle_type": "Staff Bus", "co2e_emissions": 1969.8, "reporting_year": 2020, "quantity_liters": 735, "reporting_month": "September"}	2026-01-11 15:36:49.77515+02	2026-01-11 15:36:49.775166+02	f	1	3	3	13
181	{"fuel_type": "Diesel", "distance_km": 5440, "vehicle_type": "Staff Bus", "co2e_emissions": 1822.4, "reporting_year": 2020, "quantity_liters": 680, "reporting_month": "September"}	2026-01-11 15:36:49.778756+02	2026-01-11 15:36:49.778774+02	f	1	3	3	13
182	{"fuel_type": "Gasoline", "distance_km": 1230, "vehicle_type": "Administrative Car", "co2e_emissions": 284.13, "reporting_year": 2020, "quantity_liters": 123, "reporting_month": "September"}	2026-01-11 15:36:49.783462+02	2026-01-11 15:36:49.783475+02	f	1	3	3	13
183	{"fuel_type": "Gasoline", "distance_km": 1000, "vehicle_type": "Administrative Car", "co2e_emissions": 231.0, "reporting_year": 2020, "quantity_liters": 100, "reporting_month": "September"}	2026-01-11 15:36:49.787039+02	2026-01-11 15:36:49.78705+02	f	1	3	3	13
184	{"fuel_type": "Diesel", "distance_km": 1496, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 501.16, "reporting_year": 2020, "quantity_liters": 187, "reporting_month": "September"}	2026-01-11 15:36:49.790832+02	2026-01-11 15:36:49.790847+02	f	1	3	3	13
185	{"fuel_type": "Gasoline", "distance_km": 830, "vehicle_type": "Security Patrol", "co2e_emissions": 191.73, "reporting_year": 2020, "quantity_liters": 83, "reporting_month": "September"}	2026-01-11 15:36:49.798912+02	2026-01-11 15:36:49.798927+02	f	1	3	3	13
186	{"fuel_type": "Diesel", "distance_km": 6288, "vehicle_type": "Staff Bus", "co2e_emissions": 2106.48, "reporting_year": 2020, "quantity_liters": 786, "reporting_month": "October"}	2026-01-11 15:36:49.807804+02	2026-01-11 15:36:49.807819+02	f	1	3	3	13
187	{"fuel_type": "Diesel", "distance_km": 6008, "vehicle_type": "Staff Bus", "co2e_emissions": 2012.68, "reporting_year": 2020, "quantity_liters": 751, "reporting_month": "October"}	2026-01-11 15:36:49.811591+02	2026-01-11 15:36:49.811604+02	f	1	3	3	13
188	{"fuel_type": "Gasoline", "distance_km": 1190, "vehicle_type": "Administrative Car", "co2e_emissions": 274.89, "reporting_year": 2020, "quantity_liters": 119, "reporting_month": "October"}	2026-01-11 15:36:49.815148+02	2026-01-11 15:36:49.815161+02	f	1	3	3	13
189	{"fuel_type": "Gasoline", "distance_km": 1070, "vehicle_type": "Administrative Car", "co2e_emissions": 247.17, "reporting_year": 2020, "quantity_liters": 107, "reporting_month": "October"}	2026-01-11 15:36:49.819934+02	2026-01-11 15:36:49.819953+02	f	1	3	3	13
190	{"fuel_type": "Diesel", "distance_km": 1496, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 501.16, "reporting_year": 2020, "quantity_liters": 187, "reporting_month": "October"}	2026-01-11 15:36:49.824099+02	2026-01-11 15:36:49.824113+02	f	1	3	3	13
191	{"fuel_type": "Gasoline", "distance_km": 960, "vehicle_type": "Security Patrol", "co2e_emissions": 221.76, "reporting_year": 2020, "quantity_liters": 96, "reporting_month": "October"}	2026-01-11 15:36:49.82767+02	2026-01-11 15:36:49.827681+02	f	1	3	3	13
192	{"fuel_type": "Diesel", "distance_km": 6768, "vehicle_type": "Staff Bus", "co2e_emissions": 2267.28, "reporting_year": 2020, "quantity_liters": 846, "reporting_month": "November"}	2026-01-11 15:36:49.831374+02	2026-01-11 15:36:49.831387+02	f	1	3	3	13
193	{"fuel_type": "Diesel", "distance_km": 5760, "vehicle_type": "Staff Bus", "co2e_emissions": 1929.6, "reporting_year": 2020, "quantity_liters": 720, "reporting_month": "November"}	2026-01-11 15:36:49.835397+02	2026-01-11 15:36:49.83542+02	f	1	3	3	13
194	{"fuel_type": "Gasoline", "distance_km": 1160, "vehicle_type": "Administrative Car", "co2e_emissions": 267.96, "reporting_year": 2020, "quantity_liters": 116, "reporting_month": "November"}	2026-01-11 15:36:49.840446+02	2026-01-11 15:36:49.840462+02	f	1	3	3	13
195	{"fuel_type": "Gasoline", "distance_km": 950, "vehicle_type": "Administrative Car", "co2e_emissions": 219.45, "reporting_year": 2020, "quantity_liters": 95, "reporting_month": "November"}	2026-01-11 15:36:49.845985+02	2026-01-11 15:36:49.845999+02	f	1	3	3	13
196	{"fuel_type": "Diesel", "distance_km": 1304, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 436.84, "reporting_year": 2020, "quantity_liters": 163, "reporting_month": "November"}	2026-01-11 15:36:49.849729+02	2026-01-11 15:36:49.849742+02	f	1	3	3	13
197	{"fuel_type": "Gasoline", "distance_km": 850, "vehicle_type": "Security Patrol", "co2e_emissions": 196.35, "reporting_year": 2020, "quantity_liters": 85, "reporting_month": "November"}	2026-01-11 15:36:49.853727+02	2026-01-11 15:36:49.853744+02	f	1	3	3	13
198	{"fuel_type": "Diesel", "distance_km": 5568, "vehicle_type": "Staff Bus", "co2e_emissions": 1865.28, "reporting_year": 2020, "quantity_liters": 696, "reporting_month": "December"}	2026-01-11 15:36:49.860297+02	2026-01-11 15:36:49.860311+02	f	1	3	3	13
199	{"fuel_type": "Diesel", "distance_km": 5112, "vehicle_type": "Staff Bus", "co2e_emissions": 1712.52, "reporting_year": 2020, "quantity_liters": 639, "reporting_month": "December"}	2026-01-11 15:36:49.86507+02	2026-01-11 15:36:49.865085+02	f	1	3	3	13
200	{"fuel_type": "Gasoline", "distance_km": 1010, "vehicle_type": "Administrative Car", "co2e_emissions": 233.31, "reporting_year": 2020, "quantity_liters": 101, "reporting_month": "December"}	2026-01-11 15:36:49.868969+02	2026-01-11 15:36:49.868986+02	f	1	3	3	13
201	{"fuel_type": "Gasoline", "distance_km": 890, "vehicle_type": "Administrative Car", "co2e_emissions": 205.59, "reporting_year": 2020, "quantity_liters": 89, "reporting_month": "December"}	2026-01-11 15:36:49.872646+02	2026-01-11 15:36:49.872661+02	f	1	3	3	13
202	{"fuel_type": "Diesel", "distance_km": 1152, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 385.92, "reporting_year": 2020, "quantity_liters": 144, "reporting_month": "December"}	2026-01-11 15:36:49.876661+02	2026-01-11 15:36:49.876674+02	f	1	3	3	13
203	{"fuel_type": "Gasoline", "distance_km": 830, "vehicle_type": "Security Patrol", "co2e_emissions": 191.73, "reporting_year": 2020, "quantity_liters": 83, "reporting_month": "December"}	2026-01-11 15:36:49.881038+02	2026-01-11 15:36:49.88105+02	f	1	3	3	13
204	{"fuel_type": "Diesel", "distance_km": 6320, "vehicle_type": "Staff Bus", "co2e_emissions": 2117.2, "reporting_year": 2021, "quantity_liters": 790, "reporting_month": "January"}	2026-01-11 15:36:49.884748+02	2026-01-11 15:36:49.884764+02	f	1	3	3	13
205	{"fuel_type": "Diesel", "distance_km": 5296, "vehicle_type": "Staff Bus", "co2e_emissions": 1774.16, "reporting_year": 2021, "quantity_liters": 662, "reporting_month": "January"}	2026-01-11 15:36:49.888549+02	2026-01-11 15:36:49.888568+02	f	1	3	3	13
206	{"fuel_type": "Gasoline", "distance_km": 1120, "vehicle_type": "Administrative Car", "co2e_emissions": 258.72, "reporting_year": 2021, "quantity_liters": 112, "reporting_month": "January"}	2026-01-11 15:36:49.892726+02	2026-01-11 15:36:49.892741+02	f	1	3	3	13
207	{"fuel_type": "Gasoline", "distance_km": 990, "vehicle_type": "Administrative Car", "co2e_emissions": 228.69, "reporting_year": 2021, "quantity_liters": 99, "reporting_month": "January"}	2026-01-11 15:36:49.896492+02	2026-01-11 15:36:49.896507+02	f	1	3	3	13
208	{"fuel_type": "Diesel", "distance_km": 1392, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 466.32, "reporting_year": 2021, "quantity_liters": 174, "reporting_month": "January"}	2026-01-11 15:36:49.900635+02	2026-01-11 15:36:49.900658+02	f	1	3	3	13
209	{"fuel_type": "Gasoline", "distance_km": 830, "vehicle_type": "Security Patrol", "co2e_emissions": 191.73, "reporting_year": 2021, "quantity_liters": 83, "reporting_month": "January"}	2026-01-11 15:36:49.904488+02	2026-01-11 15:36:49.904503+02	f	1	3	3	13
210	{"fuel_type": "Diesel", "distance_km": 6048, "vehicle_type": "Staff Bus", "co2e_emissions": 2026.08, "reporting_year": 2021, "quantity_liters": 756, "reporting_month": "February"}	2026-01-11 15:36:49.908423+02	2026-01-11 15:36:49.908437+02	f	1	3	3	13
211	{"fuel_type": "Diesel", "distance_km": 6024, "vehicle_type": "Staff Bus", "co2e_emissions": 2018.04, "reporting_year": 2021, "quantity_liters": 753, "reporting_month": "February"}	2026-01-11 15:36:49.913477+02	2026-01-11 15:36:49.913492+02	f	1	3	3	13
212	{"fuel_type": "Gasoline", "distance_km": 1130, "vehicle_type": "Administrative Car", "co2e_emissions": 261.03, "reporting_year": 2021, "quantity_liters": 113, "reporting_month": "February"}	2026-01-11 15:36:49.917662+02	2026-01-11 15:36:49.917677+02	f	1	3	3	13
213	{"fuel_type": "Gasoline", "distance_km": 970, "vehicle_type": "Administrative Car", "co2e_emissions": 224.07, "reporting_year": 2021, "quantity_liters": 97, "reporting_month": "February"}	2026-01-11 15:36:49.921554+02	2026-01-11 15:36:49.92157+02	f	1	3	3	13
214	{"fuel_type": "Diesel", "distance_km": 1568, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 525.28, "reporting_year": 2021, "quantity_liters": 196, "reporting_month": "February"}	2026-01-11 15:36:49.925539+02	2026-01-11 15:36:49.925566+02	f	1	3	3	13
215	{"fuel_type": "Gasoline", "distance_km": 850, "vehicle_type": "Security Patrol", "co2e_emissions": 196.35, "reporting_year": 2021, "quantity_liters": 85, "reporting_month": "February"}	2026-01-11 15:36:49.93062+02	2026-01-11 15:36:49.930636+02	f	1	3	3	13
216	{"fuel_type": "Diesel", "distance_km": 6984, "vehicle_type": "Staff Bus", "co2e_emissions": 2339.64, "reporting_year": 2021, "quantity_liters": 873, "reporting_month": "March"}	2026-01-11 15:36:49.934521+02	2026-01-11 15:36:49.934535+02	f	1	3	3	13
217	{"fuel_type": "Diesel", "distance_km": 5712, "vehicle_type": "Staff Bus", "co2e_emissions": 1913.52, "reporting_year": 2021, "quantity_liters": 714, "reporting_month": "March"}	2026-01-11 15:36:49.940275+02	2026-01-11 15:36:49.94029+02	f	1	3	3	13
218	{"fuel_type": "Gasoline", "distance_km": 1180, "vehicle_type": "Administrative Car", "co2e_emissions": 272.58, "reporting_year": 2021, "quantity_liters": 118, "reporting_month": "March"}	2026-01-11 15:36:49.943824+02	2026-01-11 15:36:49.943839+02	f	1	3	3	13
219	{"fuel_type": "Gasoline", "distance_km": 910, "vehicle_type": "Administrative Car", "co2e_emissions": 210.21, "reporting_year": 2021, "quantity_liters": 91, "reporting_month": "March"}	2026-01-11 15:36:49.947487+02	2026-01-11 15:36:49.947503+02	f	1	3	3	13
220	{"fuel_type": "Diesel", "distance_km": 1392, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 466.32, "reporting_year": 2021, "quantity_liters": 174, "reporting_month": "March"}	2026-01-11 15:36:49.952476+02	2026-01-11 15:36:49.952491+02	f	1	3	3	13
221	{"fuel_type": "Gasoline", "distance_km": 900, "vehicle_type": "Security Patrol", "co2e_emissions": 207.9, "reporting_year": 2021, "quantity_liters": 90, "reporting_month": "March"}	2026-01-11 15:36:49.959202+02	2026-01-11 15:36:49.959214+02	f	1	3	3	13
222	{"fuel_type": "Diesel", "distance_km": 6384, "vehicle_type": "Staff Bus", "co2e_emissions": 2138.64, "reporting_year": 2021, "quantity_liters": 798, "reporting_month": "April"}	2026-01-11 15:36:49.96312+02	2026-01-11 15:36:49.963135+02	f	1	3	3	13
223	{"fuel_type": "Diesel", "distance_km": 6136, "vehicle_type": "Staff Bus", "co2e_emissions": 2055.56, "reporting_year": 2021, "quantity_liters": 767, "reporting_month": "April"}	2026-01-11 15:36:49.966891+02	2026-01-11 15:36:49.966907+02	f	1	3	3	13
224	{"fuel_type": "Gasoline", "distance_km": 1310, "vehicle_type": "Administrative Car", "co2e_emissions": 302.61, "reporting_year": 2021, "quantity_liters": 131, "reporting_month": "April"}	2026-01-11 15:36:49.972133+02	2026-01-11 15:36:49.972148+02	f	1	3	3	13
225	{"fuel_type": "Gasoline", "distance_km": 980, "vehicle_type": "Administrative Car", "co2e_emissions": 226.38, "reporting_year": 2021, "quantity_liters": 98, "reporting_month": "April"}	2026-01-11 15:36:49.975988+02	2026-01-11 15:36:49.976003+02	f	1	3	3	13
226	{"fuel_type": "Diesel", "distance_km": 1528, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 511.88, "reporting_year": 2021, "quantity_liters": 191, "reporting_month": "April"}	2026-01-11 15:36:49.982804+02	2026-01-11 15:36:49.982822+02	f	1	3	3	13
227	{"fuel_type": "Gasoline", "distance_km": 840, "vehicle_type": "Security Patrol", "co2e_emissions": 194.04, "reporting_year": 2021, "quantity_liters": 84, "reporting_month": "April"}	2026-01-11 15:36:49.986849+02	2026-01-11 15:36:49.986863+02	f	1	3	3	13
228	{"fuel_type": "Diesel", "distance_km": 5480, "vehicle_type": "Staff Bus", "co2e_emissions": 1835.8, "reporting_year": 2021, "quantity_liters": 685, "reporting_month": "May"}	2026-01-11 15:36:49.990987+02	2026-01-11 15:36:49.991+02	f	1	3	3	13
229	{"fuel_type": "Diesel", "distance_km": 5088, "vehicle_type": "Staff Bus", "co2e_emissions": 1704.48, "reporting_year": 2021, "quantity_liters": 636, "reporting_month": "May"}	2026-01-11 15:36:49.995187+02	2026-01-11 15:36:49.995202+02	f	1	3	3	13
230	{"fuel_type": "Gasoline", "distance_km": 1090, "vehicle_type": "Administrative Car", "co2e_emissions": 251.79, "reporting_year": 2021, "quantity_liters": 109, "reporting_month": "May"}	2026-01-11 15:36:50.000044+02	2026-01-11 15:36:50.00006+02	f	1	3	3	13
231	{"fuel_type": "Gasoline", "distance_km": 920, "vehicle_type": "Administrative Car", "co2e_emissions": 212.52, "reporting_year": 2021, "quantity_liters": 92, "reporting_month": "May"}	2026-01-11 15:36:50.004183+02	2026-01-11 15:36:50.004198+02	f	1	3	3	13
232	{"fuel_type": "Diesel", "distance_km": 1408, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 471.68, "reporting_year": 2021, "quantity_liters": 176, "reporting_month": "May"}	2026-01-11 15:36:50.008066+02	2026-01-11 15:36:50.008084+02	f	1	3	3	13
233	{"fuel_type": "Gasoline", "distance_km": 740, "vehicle_type": "Security Patrol", "co2e_emissions": 170.94, "reporting_year": 2021, "quantity_liters": 74, "reporting_month": "May"}	2026-01-11 15:36:50.012279+02	2026-01-11 15:36:50.012294+02	f	1	3	3	13
234	{"fuel_type": "Diesel", "distance_km": 4656, "vehicle_type": "Staff Bus", "co2e_emissions": 1559.76, "reporting_year": 2021, "quantity_liters": 582, "reporting_month": "June"}	2026-01-11 15:36:50.016235+02	2026-01-11 15:36:50.016249+02	f	1	3	3	13
235	{"fuel_type": "Diesel", "distance_km": 4504, "vehicle_type": "Staff Bus", "co2e_emissions": 1508.84, "reporting_year": 2021, "quantity_liters": 563, "reporting_month": "June"}	2026-01-11 15:36:50.021291+02	2026-01-11 15:36:50.021304+02	f	1	3	3	13
236	{"fuel_type": "Gasoline", "distance_km": 920, "vehicle_type": "Administrative Car", "co2e_emissions": 212.52, "reporting_year": 2021, "quantity_liters": 92, "reporting_month": "June"}	2026-01-11 15:36:50.025817+02	2026-01-11 15:36:50.025838+02	f	1	3	3	13
237	{"fuel_type": "Gasoline", "distance_km": 750, "vehicle_type": "Administrative Car", "co2e_emissions": 173.25, "reporting_year": 2021, "quantity_liters": 75, "reporting_month": "June"}	2026-01-11 15:36:50.029876+02	2026-01-11 15:36:50.02989+02	f	1	3	3	13
238	{"fuel_type": "Diesel", "distance_km": 1016, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 340.36, "reporting_year": 2021, "quantity_liters": 127, "reporting_month": "June"}	2026-01-11 15:36:50.03461+02	2026-01-11 15:36:50.034624+02	f	1	3	3	13
239	{"fuel_type": "Gasoline", "distance_km": 640, "vehicle_type": "Security Patrol", "co2e_emissions": 147.84, "reporting_year": 2021, "quantity_liters": 64, "reporting_month": "June"}	2026-01-11 15:36:50.039012+02	2026-01-11 15:36:50.03903+02	f	1	3	3	13
240	{"fuel_type": "Diesel", "distance_km": 2808, "vehicle_type": "Staff Bus", "co2e_emissions": 940.68, "reporting_year": 2021, "quantity_liters": 351, "reporting_month": "July"}	2026-01-11 15:36:50.044488+02	2026-01-11 15:36:50.044504+02	f	1	3	3	13
241	{"fuel_type": "Diesel", "distance_km": 2192, "vehicle_type": "Staff Bus", "co2e_emissions": 734.32, "reporting_year": 2021, "quantity_liters": 274, "reporting_month": "July"}	2026-01-11 15:36:50.048215+02	2026-01-11 15:36:50.04823+02	f	1	3	3	13
242	{"fuel_type": "Gasoline", "distance_km": 440, "vehicle_type": "Administrative Car", "co2e_emissions": 101.64, "reporting_year": 2021, "quantity_liters": 44, "reporting_month": "July"}	2026-01-11 15:36:50.051645+02	2026-01-11 15:36:50.051659+02	f	1	3	3	13
243	{"fuel_type": "Gasoline", "distance_km": 410, "vehicle_type": "Administrative Car", "co2e_emissions": 94.71, "reporting_year": 2021, "quantity_liters": 41, "reporting_month": "July"}	2026-01-11 15:36:50.057832+02	2026-01-11 15:36:50.057848+02	f	1	3	3	13
244	{"fuel_type": "Diesel", "distance_km": 568, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 190.28, "reporting_year": 2021, "quantity_liters": 71, "reporting_month": "July"}	2026-01-11 15:36:50.061717+02	2026-01-11 15:36:50.061732+02	f	1	3	3	13
245	{"fuel_type": "Gasoline", "distance_km": 370, "vehicle_type": "Security Patrol", "co2e_emissions": 85.47, "reporting_year": 2021, "quantity_liters": 37, "reporting_month": "July"}	2026-01-11 15:36:50.065542+02	2026-01-11 15:36:50.065585+02	f	1	3	3	13
246	{"fuel_type": "Diesel", "distance_km": 1880, "vehicle_type": "Staff Bus", "co2e_emissions": 629.8, "reporting_year": 2021, "quantity_liters": 235, "reporting_month": "August"}	2026-01-11 15:36:50.070809+02	2026-01-11 15:36:50.070827+02	f	1	3	3	13
247	{"fuel_type": "Diesel", "distance_km": 1736, "vehicle_type": "Staff Bus", "co2e_emissions": 581.56, "reporting_year": 2021, "quantity_liters": 217, "reporting_month": "August"}	2026-01-11 15:36:50.074826+02	2026-01-11 15:36:50.07485+02	f	1	3	3	13
248	{"fuel_type": "Gasoline", "distance_km": 380, "vehicle_type": "Administrative Car", "co2e_emissions": 87.78, "reporting_year": 2021, "quantity_liters": 38, "reporting_month": "August"}	2026-01-11 15:36:50.081587+02	2026-01-11 15:36:50.081602+02	f	1	3	3	13
249	{"fuel_type": "Gasoline", "distance_km": 280, "vehicle_type": "Administrative Car", "co2e_emissions": 64.68, "reporting_year": 2021, "quantity_liters": 28, "reporting_month": "August"}	2026-01-11 15:36:50.085178+02	2026-01-11 15:36:50.085191+02	f	1	3	3	13
250	{"fuel_type": "Diesel", "distance_km": 440, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 147.4, "reporting_year": 2021, "quantity_liters": 55, "reporting_month": "August"}	2026-01-11 15:36:50.089914+02	2026-01-11 15:36:50.089929+02	f	1	3	3	13
251	{"fuel_type": "Gasoline", "distance_km": 250, "vehicle_type": "Security Patrol", "co2e_emissions": 57.75, "reporting_year": 2021, "quantity_liters": 25, "reporting_month": "August"}	2026-01-11 15:36:50.0935+02	2026-01-11 15:36:50.093512+02	f	1	3	3	13
252	{"fuel_type": "Diesel", "distance_km": 6432, "vehicle_type": "Staff Bus", "co2e_emissions": 2154.72, "reporting_year": 2021, "quantity_liters": 804, "reporting_month": "September"}	2026-01-11 15:36:50.096883+02	2026-01-11 15:36:50.096895+02	f	1	3	3	13
253	{"fuel_type": "Diesel", "distance_km": 5872, "vehicle_type": "Staff Bus", "co2e_emissions": 1967.12, "reporting_year": 2021, "quantity_liters": 734, "reporting_month": "September"}	2026-01-11 15:36:50.102344+02	2026-01-11 15:36:50.10236+02	f	1	3	3	13
254	{"fuel_type": "Gasoline", "distance_km": 1150, "vehicle_type": "Administrative Car", "co2e_emissions": 265.65, "reporting_year": 2021, "quantity_liters": 115, "reporting_month": "September"}	2026-01-11 15:36:50.10654+02	2026-01-11 15:36:50.106556+02	f	1	3	3	13
255	{"fuel_type": "Gasoline", "distance_km": 1040, "vehicle_type": "Administrative Car", "co2e_emissions": 240.24, "reporting_year": 2021, "quantity_liters": 104, "reporting_month": "September"}	2026-01-11 15:36:50.110301+02	2026-01-11 15:36:50.110313+02	f	1	3	3	13
256	{"fuel_type": "Diesel", "distance_km": 1440, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 482.4, "reporting_year": 2021, "quantity_liters": 180, "reporting_month": "September"}	2026-01-11 15:36:50.114263+02	2026-01-11 15:36:50.114278+02	f	1	3	3	13
257	{"fuel_type": "Gasoline", "distance_km": 910, "vehicle_type": "Security Patrol", "co2e_emissions": 210.21, "reporting_year": 2021, "quantity_liters": 91, "reporting_month": "September"}	2026-01-11 15:36:50.118814+02	2026-01-11 15:36:50.118835+02	f	1	3	3	13
258	{"fuel_type": "Diesel", "distance_km": 6152, "vehicle_type": "Staff Bus", "co2e_emissions": 2060.92, "reporting_year": 2021, "quantity_liters": 769, "reporting_month": "October"}	2026-01-11 15:36:50.123118+02	2026-01-11 15:36:50.123135+02	f	1	3	3	13
259	{"fuel_type": "Diesel", "distance_km": 5704, "vehicle_type": "Staff Bus", "co2e_emissions": 1910.84, "reporting_year": 2021, "quantity_liters": 713, "reporting_month": "October"}	2026-01-11 15:36:50.12709+02	2026-01-11 15:36:50.127105+02	f	1	3	3	13
260	{"fuel_type": "Gasoline", "distance_km": 1210, "vehicle_type": "Administrative Car", "co2e_emissions": 279.51, "reporting_year": 2021, "quantity_liters": 121, "reporting_month": "October"}	2026-01-11 15:36:50.131218+02	2026-01-11 15:36:50.131235+02	f	1	3	3	13
261	{"fuel_type": "Gasoline", "distance_km": 950, "vehicle_type": "Administrative Car", "co2e_emissions": 219.45, "reporting_year": 2021, "quantity_liters": 95, "reporting_month": "October"}	2026-01-11 15:36:50.13562+02	2026-01-11 15:36:50.135637+02	f	1	3	3	13
262	{"fuel_type": "Diesel", "distance_km": 1528, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 511.88, "reporting_year": 2021, "quantity_liters": 191, "reporting_month": "October"}	2026-01-11 15:36:50.139493+02	2026-01-11 15:36:50.139507+02	f	1	3	3	13
263	{"fuel_type": "Gasoline", "distance_km": 970, "vehicle_type": "Security Patrol", "co2e_emissions": 224.07, "reporting_year": 2021, "quantity_liters": 97, "reporting_month": "October"}	2026-01-11 15:36:50.144281+02	2026-01-11 15:36:50.144299+02	f	1	3	3	13
264	{"fuel_type": "Diesel", "distance_km": 6640, "vehicle_type": "Staff Bus", "co2e_emissions": 2224.4, "reporting_year": 2021, "quantity_liters": 830, "reporting_month": "November"}	2026-01-11 15:36:50.148801+02	2026-01-11 15:36:50.148837+02	f	1	3	3	13
265	{"fuel_type": "Diesel", "distance_km": 6592, "vehicle_type": "Staff Bus", "co2e_emissions": 2208.32, "reporting_year": 2021, "quantity_liters": 824, "reporting_month": "November"}	2026-01-11 15:36:50.156103+02	2026-01-11 15:36:50.156118+02	f	1	3	3	13
266	{"fuel_type": "Gasoline", "distance_km": 1280, "vehicle_type": "Administrative Car", "co2e_emissions": 295.68, "reporting_year": 2021, "quantity_liters": 128, "reporting_month": "November"}	2026-01-11 15:36:50.163613+02	2026-01-11 15:36:50.16363+02	f	1	3	3	13
267	{"fuel_type": "Gasoline", "distance_km": 1100, "vehicle_type": "Administrative Car", "co2e_emissions": 254.1, "reporting_year": 2021, "quantity_liters": 110, "reporting_month": "November"}	2026-01-11 15:36:50.167466+02	2026-01-11 15:36:50.167482+02	f	1	3	3	13
268	{"fuel_type": "Diesel", "distance_km": 1304, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 436.84, "reporting_year": 2021, "quantity_liters": 163, "reporting_month": "November"}	2026-01-11 15:36:50.171069+02	2026-01-11 15:36:50.171084+02	f	1	3	3	13
269	{"fuel_type": "Gasoline", "distance_km": 960, "vehicle_type": "Security Patrol", "co2e_emissions": 221.76, "reporting_year": 2021, "quantity_liters": 96, "reporting_month": "November"}	2026-01-11 15:36:50.174619+02	2026-01-11 15:36:50.174634+02	f	1	3	3	13
270	{"fuel_type": "Diesel", "distance_km": 6024, "vehicle_type": "Staff Bus", "co2e_emissions": 2018.04, "reporting_year": 2021, "quantity_liters": 753, "reporting_month": "December"}	2026-01-11 15:36:50.17938+02	2026-01-11 15:36:50.179395+02	f	1	3	3	13
271	{"fuel_type": "Diesel", "distance_km": 5216, "vehicle_type": "Staff Bus", "co2e_emissions": 1747.36, "reporting_year": 2021, "quantity_liters": 652, "reporting_month": "December"}	2026-01-11 15:36:50.183667+02	2026-01-11 15:36:50.183683+02	f	1	3	3	13
272	{"fuel_type": "Gasoline", "distance_km": 960, "vehicle_type": "Administrative Car", "co2e_emissions": 221.76, "reporting_year": 2021, "quantity_liters": 96, "reporting_month": "December"}	2026-01-11 15:36:50.187741+02	2026-01-11 15:36:50.187757+02	f	1	3	3	13
273	{"fuel_type": "Gasoline", "distance_km": 900, "vehicle_type": "Administrative Car", "co2e_emissions": 207.9, "reporting_year": 2021, "quantity_liters": 90, "reporting_month": "December"}	2026-01-11 15:36:50.191648+02	2026-01-11 15:36:50.191666+02	f	1	3	3	13
274	{"fuel_type": "Diesel", "distance_km": 1216, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 407.36, "reporting_year": 2021, "quantity_liters": 152, "reporting_month": "December"}	2026-01-11 15:36:50.202209+02	2026-01-11 15:36:50.202229+02	f	1	3	3	13
275	{"fuel_type": "Gasoline", "distance_km": 730, "vehicle_type": "Security Patrol", "co2e_emissions": 168.63, "reporting_year": 2021, "quantity_liters": 73, "reporting_month": "December"}	2026-01-11 15:36:50.206157+02	2026-01-11 15:36:50.20617+02	f	1	3	3	13
276	{"fuel_type": "Diesel", "distance_km": 6448, "vehicle_type": "Staff Bus", "co2e_emissions": 2160.08, "reporting_year": 2022, "quantity_liters": 806, "reporting_month": "January"}	2026-01-11 15:36:50.209642+02	2026-01-11 15:36:50.209653+02	f	1	3	3	13
277	{"fuel_type": "Diesel", "distance_km": 5936, "vehicle_type": "Staff Bus", "co2e_emissions": 1988.56, "reporting_year": 2022, "quantity_liters": 742, "reporting_month": "January"}	2026-01-11 15:36:50.213593+02	2026-01-11 15:36:50.213609+02	f	1	3	3	13
278	{"fuel_type": "Gasoline", "distance_km": 1090, "vehicle_type": "Administrative Car", "co2e_emissions": 251.79, "reporting_year": 2022, "quantity_liters": 109, "reporting_month": "January"}	2026-01-11 15:36:50.217714+02	2026-01-11 15:36:50.21774+02	f	1	3	3	13
279	{"fuel_type": "Gasoline", "distance_km": 830, "vehicle_type": "Administrative Car", "co2e_emissions": 191.73, "reporting_year": 2022, "quantity_liters": 83, "reporting_month": "January"}	2026-01-11 15:36:50.222802+02	2026-01-11 15:36:50.222818+02	f	1	3	3	13
280	{"fuel_type": "Diesel", "distance_km": 1272, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 426.12, "reporting_year": 2022, "quantity_liters": 159, "reporting_month": "January"}	2026-01-11 15:36:50.226877+02	2026-01-11 15:36:50.226897+02	f	1	3	3	13
281	{"fuel_type": "Gasoline", "distance_km": 820, "vehicle_type": "Security Patrol", "co2e_emissions": 189.42, "reporting_year": 2022, "quantity_liters": 82, "reporting_month": "January"}	2026-01-11 15:36:50.231132+02	2026-01-11 15:36:50.231149+02	f	1	3	3	13
282	{"fuel_type": "Diesel", "distance_km": 5960, "vehicle_type": "Staff Bus", "co2e_emissions": 1996.6, "reporting_year": 2022, "quantity_liters": 745, "reporting_month": "February"}	2026-01-11 15:36:50.234918+02	2026-01-11 15:36:50.234933+02	f	1	3	3	13
283	{"fuel_type": "Diesel", "distance_km": 6272, "vehicle_type": "Staff Bus", "co2e_emissions": 2101.12, "reporting_year": 2022, "quantity_liters": 784, "reporting_month": "February"}	2026-01-11 15:36:50.238726+02	2026-01-11 15:36:50.23874+02	f	1	3	3	13
284	{"fuel_type": "Gasoline", "distance_km": 1180, "vehicle_type": "Administrative Car", "co2e_emissions": 272.58, "reporting_year": 2022, "quantity_liters": 118, "reporting_month": "February"}	2026-01-11 15:36:50.243462+02	2026-01-11 15:36:50.243481+02	f	1	3	3	13
285	{"fuel_type": "Gasoline", "distance_km": 1060, "vehicle_type": "Administrative Car", "co2e_emissions": 244.86, "reporting_year": 2022, "quantity_liters": 106, "reporting_month": "February"}	2026-01-11 15:36:50.247762+02	2026-01-11 15:36:50.247778+02	f	1	3	3	13
286	{"fuel_type": "Diesel", "distance_km": 1424, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 477.04, "reporting_year": 2022, "quantity_liters": 178, "reporting_month": "February"}	2026-01-11 15:36:50.251255+02	2026-01-11 15:36:50.25127+02	f	1	3	3	13
287	{"fuel_type": "Gasoline", "distance_km": 950, "vehicle_type": "Security Patrol", "co2e_emissions": 219.45, "reporting_year": 2022, "quantity_liters": 95, "reporting_month": "February"}	2026-01-11 15:36:50.254499+02	2026-01-11 15:36:50.254513+02	f	1	3	3	13
288	{"fuel_type": "Diesel", "distance_km": 6600, "vehicle_type": "Staff Bus", "co2e_emissions": 2211.0, "reporting_year": 2022, "quantity_liters": 825, "reporting_month": "March"}	2026-01-11 15:36:50.2579+02	2026-01-11 15:36:50.257916+02	f	1	3	3	13
289	{"fuel_type": "Diesel", "distance_km": 5568, "vehicle_type": "Staff Bus", "co2e_emissions": 1865.28, "reporting_year": 2022, "quantity_liters": 696, "reporting_month": "March"}	2026-01-11 15:36:50.263012+02	2026-01-11 15:36:50.26303+02	f	1	3	3	13
290	{"fuel_type": "Gasoline", "distance_km": 1210, "vehicle_type": "Administrative Car", "co2e_emissions": 279.51, "reporting_year": 2022, "quantity_liters": 121, "reporting_month": "March"}	2026-01-11 15:36:50.268322+02	2026-01-11 15:36:50.268336+02	f	1	3	3	13
291	{"fuel_type": "Gasoline", "distance_km": 920, "vehicle_type": "Administrative Car", "co2e_emissions": 212.52, "reporting_year": 2022, "quantity_liters": 92, "reporting_month": "March"}	2026-01-11 15:36:50.274871+02	2026-01-11 15:36:50.274893+02	f	1	3	3	13
292	{"fuel_type": "Diesel", "distance_km": 1608, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 538.68, "reporting_year": 2022, "quantity_liters": 201, "reporting_month": "March"}	2026-01-11 15:36:50.279041+02	2026-01-11 15:36:50.279058+02	f	1	3	3	13
293	{"fuel_type": "Gasoline", "distance_km": 890, "vehicle_type": "Security Patrol", "co2e_emissions": 205.59, "reporting_year": 2022, "quantity_liters": 89, "reporting_month": "March"}	2026-01-11 15:36:50.282574+02	2026-01-11 15:36:50.282589+02	f	1	3	3	13
294	{"fuel_type": "Diesel", "distance_km": 6224, "vehicle_type": "Staff Bus", "co2e_emissions": 2085.04, "reporting_year": 2022, "quantity_liters": 778, "reporting_month": "April"}	2026-01-11 15:36:50.28655+02	2026-01-11 15:36:50.286565+02	f	1	3	3	13
295	{"fuel_type": "Diesel", "distance_km": 6000, "vehicle_type": "Staff Bus", "co2e_emissions": 2010.0, "reporting_year": 2022, "quantity_liters": 750, "reporting_month": "April"}	2026-01-11 15:36:50.291465+02	2026-01-11 15:36:50.291483+02	f	1	3	3	13
296	{"fuel_type": "Gasoline", "distance_km": 1210, "vehicle_type": "Administrative Car", "co2e_emissions": 279.51, "reporting_year": 2022, "quantity_liters": 121, "reporting_month": "April"}	2026-01-11 15:36:50.295509+02	2026-01-11 15:36:50.295531+02	f	1	3	3	13
297	{"fuel_type": "Gasoline", "distance_km": 1020, "vehicle_type": "Administrative Car", "co2e_emissions": 235.62, "reporting_year": 2022, "quantity_liters": 102, "reporting_month": "April"}	2026-01-11 15:36:50.299269+02	2026-01-11 15:36:50.299285+02	f	1	3	3	13
298	{"fuel_type": "Diesel", "distance_km": 1408, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 471.68, "reporting_year": 2022, "quantity_liters": 176, "reporting_month": "April"}	2026-01-11 15:36:50.302943+02	2026-01-11 15:36:50.302958+02	f	1	3	3	13
299	{"fuel_type": "Gasoline", "distance_km": 880, "vehicle_type": "Security Patrol", "co2e_emissions": 203.28, "reporting_year": 2022, "quantity_liters": 88, "reporting_month": "April"}	2026-01-11 15:36:50.307789+02	2026-01-11 15:36:50.307814+02	f	1	3	3	13
300	{"fuel_type": "Diesel", "distance_km": 6232, "vehicle_type": "Staff Bus", "co2e_emissions": 2087.72, "reporting_year": 2022, "quantity_liters": 779, "reporting_month": "May"}	2026-01-11 15:36:50.313298+02	2026-01-11 15:36:50.313315+02	f	1	3	3	13
301	{"fuel_type": "Diesel", "distance_km": 4984, "vehicle_type": "Staff Bus", "co2e_emissions": 1669.64, "reporting_year": 2022, "quantity_liters": 623, "reporting_month": "May"}	2026-01-11 15:36:50.317243+02	2026-01-11 15:36:50.317258+02	f	1	3	3	13
302	{"fuel_type": "Gasoline", "distance_km": 990, "vehicle_type": "Administrative Car", "co2e_emissions": 228.69, "reporting_year": 2022, "quantity_liters": 99, "reporting_month": "May"}	2026-01-11 15:36:50.321407+02	2026-01-11 15:36:50.32143+02	f	1	3	3	13
303	{"fuel_type": "Gasoline", "distance_km": 850, "vehicle_type": "Administrative Car", "co2e_emissions": 196.35, "reporting_year": 2022, "quantity_liters": 85, "reporting_month": "May"}	2026-01-11 15:36:50.325967+02	2026-01-11 15:36:50.325986+02	f	1	3	3	13
304	{"fuel_type": "Diesel", "distance_km": 1280, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 428.8, "reporting_year": 2022, "quantity_liters": 160, "reporting_month": "May"}	2026-01-11 15:36:50.331161+02	2026-01-11 15:36:50.331177+02	f	1	3	3	13
305	{"fuel_type": "Gasoline", "distance_km": 750, "vehicle_type": "Security Patrol", "co2e_emissions": 173.25, "reporting_year": 2022, "quantity_liters": 75, "reporting_month": "May"}	2026-01-11 15:36:50.33661+02	2026-01-11 15:36:50.336629+02	f	1	3	3	13
306	{"fuel_type": "Diesel", "distance_km": 4504, "vehicle_type": "Staff Bus", "co2e_emissions": 1508.84, "reporting_year": 2022, "quantity_liters": 563, "reporting_month": "June"}	2026-01-11 15:36:50.340621+02	2026-01-11 15:36:50.340637+02	f	1	3	3	13
307	{"fuel_type": "Diesel", "distance_km": 3856, "vehicle_type": "Staff Bus", "co2e_emissions": 1291.76, "reporting_year": 2022, "quantity_liters": 482, "reporting_month": "June"}	2026-01-11 15:36:50.344042+02	2026-01-11 15:36:50.344056+02	f	1	3	3	13
308	{"fuel_type": "Gasoline", "distance_km": 880, "vehicle_type": "Administrative Car", "co2e_emissions": 203.28, "reporting_year": 2022, "quantity_liters": 88, "reporting_month": "June"}	2026-01-11 15:36:50.347357+02	2026-01-11 15:36:50.347372+02	f	1	3	3	13
309	{"fuel_type": "Gasoline", "distance_km": 700, "vehicle_type": "Administrative Car", "co2e_emissions": 161.7, "reporting_year": 2022, "quantity_liters": 70, "reporting_month": "June"}	2026-01-11 15:36:50.352579+02	2026-01-11 15:36:50.352599+02	f	1	3	3	13
310	{"fuel_type": "Diesel", "distance_km": 1048, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 351.08, "reporting_year": 2022, "quantity_liters": 131, "reporting_month": "June"}	2026-01-11 15:36:50.356397+02	2026-01-11 15:36:50.356413+02	f	1	3	3	13
311	{"fuel_type": "Gasoline", "distance_km": 690, "vehicle_type": "Security Patrol", "co2e_emissions": 159.39, "reporting_year": 2022, "quantity_liters": 69, "reporting_month": "June"}	2026-01-11 15:36:50.359869+02	2026-01-11 15:36:50.359891+02	f	1	3	3	13
312	{"fuel_type": "Diesel", "distance_km": 2400, "vehicle_type": "Staff Bus", "co2e_emissions": 804.0, "reporting_year": 2022, "quantity_liters": 300, "reporting_month": "July"}	2026-01-11 15:36:50.36326+02	2026-01-11 15:36:50.363273+02	f	1	3	3	13
313	{"fuel_type": "Diesel", "distance_km": 2528, "vehicle_type": "Staff Bus", "co2e_emissions": 846.88, "reporting_year": 2022, "quantity_liters": 316, "reporting_month": "July"}	2026-01-11 15:36:50.366493+02	2026-01-11 15:36:50.366507+02	f	1	3	3	13
314	{"fuel_type": "Gasoline", "distance_km": 460, "vehicle_type": "Administrative Car", "co2e_emissions": 106.26, "reporting_year": 2022, "quantity_liters": 46, "reporting_month": "July"}	2026-01-11 15:36:50.371299+02	2026-01-11 15:36:50.371315+02	f	1	3	3	13
315	{"fuel_type": "Gasoline", "distance_km": 420, "vehicle_type": "Administrative Car", "co2e_emissions": 97.02, "reporting_year": 2022, "quantity_liters": 42, "reporting_month": "July"}	2026-01-11 15:36:50.376403+02	2026-01-11 15:36:50.376419+02	f	1	3	3	13
316	{"fuel_type": "Diesel", "distance_km": 576, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 192.96, "reporting_year": 2022, "quantity_liters": 72, "reporting_month": "July"}	2026-01-11 15:36:50.380262+02	2026-01-11 15:36:50.380277+02	f	1	3	3	13
317	{"fuel_type": "Gasoline", "distance_km": 350, "vehicle_type": "Security Patrol", "co2e_emissions": 80.85, "reporting_year": 2022, "quantity_liters": 35, "reporting_month": "July"}	2026-01-11 15:36:50.384483+02	2026-01-11 15:36:50.3845+02	f	1	3	3	13
318	{"fuel_type": "Diesel", "distance_km": 2000, "vehicle_type": "Staff Bus", "co2e_emissions": 670.0, "reporting_year": 2022, "quantity_liters": 250, "reporting_month": "August"}	2026-01-11 15:36:50.388464+02	2026-01-11 15:36:50.38848+02	f	1	3	3	13
319	{"fuel_type": "Diesel", "distance_km": 1992, "vehicle_type": "Staff Bus", "co2e_emissions": 667.32, "reporting_year": 2022, "quantity_liters": 249, "reporting_month": "August"}	2026-01-11 15:36:50.392083+02	2026-01-11 15:36:50.392094+02	f	1	3	3	13
320	{"fuel_type": "Gasoline", "distance_km": 400, "vehicle_type": "Administrative Car", "co2e_emissions": 92.4, "reporting_year": 2022, "quantity_liters": 40, "reporting_month": "August"}	2026-01-11 15:36:50.395828+02	2026-01-11 15:36:50.395842+02	f	1	3	3	13
321	{"fuel_type": "Gasoline", "distance_km": 290, "vehicle_type": "Administrative Car", "co2e_emissions": 66.99, "reporting_year": 2022, "quantity_liters": 29, "reporting_month": "August"}	2026-01-11 15:36:50.39985+02	2026-01-11 15:36:50.399866+02	f	1	3	3	13
322	{"fuel_type": "Diesel", "distance_km": 424, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 142.04, "reporting_year": 2022, "quantity_liters": 53, "reporting_month": "August"}	2026-01-11 15:36:50.403854+02	2026-01-11 15:36:50.403869+02	f	1	3	3	13
323	{"fuel_type": "Gasoline", "distance_km": 290, "vehicle_type": "Security Patrol", "co2e_emissions": 66.99, "reporting_year": 2022, "quantity_liters": 29, "reporting_month": "August"}	2026-01-11 15:36:50.407549+02	2026-01-11 15:36:50.407562+02	f	1	3	3	13
324	{"fuel_type": "Diesel", "distance_km": 6488, "vehicle_type": "Staff Bus", "co2e_emissions": 2173.48, "reporting_year": 2022, "quantity_liters": 811, "reporting_month": "September"}	2026-01-11 15:36:50.411004+02	2026-01-11 15:36:50.411016+02	f	1	3	3	13
325	{"fuel_type": "Diesel", "distance_km": 6328, "vehicle_type": "Staff Bus", "co2e_emissions": 2119.88, "reporting_year": 2022, "quantity_liters": 791, "reporting_month": "September"}	2026-01-11 15:36:50.41483+02	2026-01-11 15:36:50.414846+02	f	1	3	3	13
326	{"fuel_type": "Gasoline", "distance_km": 1250, "vehicle_type": "Administrative Car", "co2e_emissions": 288.75, "reporting_year": 2022, "quantity_liters": 125, "reporting_month": "September"}	2026-01-11 15:36:50.41879+02	2026-01-11 15:36:50.418806+02	f	1	3	3	13
327	{"fuel_type": "Gasoline", "distance_km": 910, "vehicle_type": "Administrative Car", "co2e_emissions": 210.21, "reporting_year": 2022, "quantity_liters": 91, "reporting_month": "September"}	2026-01-11 15:36:50.422665+02	2026-01-11 15:36:50.422679+02	f	1	3	3	13
328	{"fuel_type": "Diesel", "distance_km": 1520, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 509.2, "reporting_year": 2022, "quantity_liters": 190, "reporting_month": "September"}	2026-01-11 15:36:50.426251+02	2026-01-11 15:36:50.426263+02	f	1	3	3	13
329	{"fuel_type": "Gasoline", "distance_km": 830, "vehicle_type": "Security Patrol", "co2e_emissions": 191.73, "reporting_year": 2022, "quantity_liters": 83, "reporting_month": "September"}	2026-01-11 15:36:50.429862+02	2026-01-11 15:36:50.429875+02	f	1	3	3	13
330	{"fuel_type": "Diesel", "distance_km": 6224, "vehicle_type": "Staff Bus", "co2e_emissions": 2085.04, "reporting_year": 2022, "quantity_liters": 778, "reporting_month": "October"}	2026-01-11 15:36:50.434398+02	2026-01-11 15:36:50.434413+02	f	1	3	3	13
331	{"fuel_type": "Diesel", "distance_km": 6000, "vehicle_type": "Staff Bus", "co2e_emissions": 2010.0, "reporting_year": 2022, "quantity_liters": 750, "reporting_month": "October"}	2026-01-11 15:36:50.438014+02	2026-01-11 15:36:50.438028+02	f	1	3	3	13
332	{"fuel_type": "Gasoline", "distance_km": 1100, "vehicle_type": "Administrative Car", "co2e_emissions": 254.1, "reporting_year": 2022, "quantity_liters": 110, "reporting_month": "October"}	2026-01-11 15:36:50.441425+02	2026-01-11 15:36:50.441439+02	f	1	3	3	13
333	{"fuel_type": "Gasoline", "distance_km": 1070, "vehicle_type": "Administrative Car", "co2e_emissions": 247.17, "reporting_year": 2022, "quantity_liters": 107, "reporting_month": "October"}	2026-01-11 15:36:50.444826+02	2026-01-11 15:36:50.44484+02	f	1	3	3	13
334	{"fuel_type": "Diesel", "distance_km": 1368, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 458.28, "reporting_year": 2022, "quantity_liters": 171, "reporting_month": "October"}	2026-01-11 15:36:50.448686+02	2026-01-11 15:36:50.448702+02	f	1	3	3	13
335	{"fuel_type": "Gasoline", "distance_km": 990, "vehicle_type": "Security Patrol", "co2e_emissions": 228.69, "reporting_year": 2022, "quantity_liters": 99, "reporting_month": "October"}	2026-01-11 15:36:50.45381+02	2026-01-11 15:36:50.453824+02	f	1	3	3	13
336	{"fuel_type": "Diesel", "distance_km": 6272, "vehicle_type": "Staff Bus", "co2e_emissions": 2101.12, "reporting_year": 2022, "quantity_liters": 784, "reporting_month": "November"}	2026-01-11 15:36:50.457473+02	2026-01-11 15:36:50.457489+02	f	1	3	3	13
337	{"fuel_type": "Diesel", "distance_km": 6360, "vehicle_type": "Staff Bus", "co2e_emissions": 2130.6, "reporting_year": 2022, "quantity_liters": 795, "reporting_month": "November"}	2026-01-11 15:36:50.461161+02	2026-01-11 15:36:50.461176+02	f	1	3	3	13
338	{"fuel_type": "Gasoline", "distance_km": 1130, "vehicle_type": "Administrative Car", "co2e_emissions": 261.03, "reporting_year": 2022, "quantity_liters": 113, "reporting_month": "November"}	2026-01-11 15:36:50.4653+02	2026-01-11 15:36:50.465339+02	f	1	3	3	13
339	{"fuel_type": "Gasoline", "distance_km": 1070, "vehicle_type": "Administrative Car", "co2e_emissions": 247.17, "reporting_year": 2022, "quantity_liters": 107, "reporting_month": "November"}	2026-01-11 15:36:50.47076+02	2026-01-11 15:36:50.470775+02	f	1	3	3	13
340	{"fuel_type": "Diesel", "distance_km": 1552, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 519.92, "reporting_year": 2022, "quantity_liters": 194, "reporting_month": "November"}	2026-01-11 15:36:50.475045+02	2026-01-11 15:36:50.475061+02	f	1	3	3	13
341	{"fuel_type": "Gasoline", "distance_km": 990, "vehicle_type": "Security Patrol", "co2e_emissions": 228.69, "reporting_year": 2022, "quantity_liters": 99, "reporting_month": "November"}	2026-01-11 15:36:50.479233+02	2026-01-11 15:36:50.479251+02	f	1	3	3	13
342	{"fuel_type": "Diesel", "distance_km": 5520, "vehicle_type": "Staff Bus", "co2e_emissions": 1849.2, "reporting_year": 2022, "quantity_liters": 690, "reporting_month": "December"}	2026-01-11 15:36:50.48312+02	2026-01-11 15:36:50.483136+02	f	1	3	3	13
343	{"fuel_type": "Diesel", "distance_km": 4832, "vehicle_type": "Staff Bus", "co2e_emissions": 1618.72, "reporting_year": 2022, "quantity_liters": 604, "reporting_month": "December"}	2026-01-11 15:36:50.487035+02	2026-01-11 15:36:50.487049+02	f	1	3	3	13
344	{"fuel_type": "Gasoline", "distance_km": 940, "vehicle_type": "Administrative Car", "co2e_emissions": 217.14, "reporting_year": 2022, "quantity_liters": 94, "reporting_month": "December"}	2026-01-11 15:36:50.49187+02	2026-01-11 15:36:50.491881+02	f	1	3	3	13
345	{"fuel_type": "Gasoline", "distance_km": 800, "vehicle_type": "Administrative Car", "co2e_emissions": 184.8, "reporting_year": 2022, "quantity_liters": 80, "reporting_month": "December"}	2026-01-11 15:36:50.495987+02	2026-01-11 15:36:50.496005+02	f	1	3	3	13
346	{"fuel_type": "Diesel", "distance_km": 1144, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 383.24, "reporting_year": 2022, "quantity_liters": 143, "reporting_month": "December"}	2026-01-11 15:36:50.500117+02	2026-01-11 15:36:50.500133+02	f	1	3	3	13
347	{"fuel_type": "Gasoline", "distance_km": 800, "vehicle_type": "Security Patrol", "co2e_emissions": 184.8, "reporting_year": 2022, "quantity_liters": 80, "reporting_month": "December"}	2026-01-11 15:36:50.504033+02	2026-01-11 15:36:50.504049+02	f	1	3	3	13
348	{"fuel_type": "Diesel", "distance_km": 6144, "vehicle_type": "Staff Bus", "co2e_emissions": 2058.24, "reporting_year": 2023, "quantity_liters": 768, "reporting_month": "January"}	2026-01-11 15:36:50.510073+02	2026-01-11 15:36:50.510104+02	f	1	3	3	13
349	{"fuel_type": "Diesel", "distance_km": 5616, "vehicle_type": "Staff Bus", "co2e_emissions": 1881.36, "reporting_year": 2023, "quantity_liters": 702, "reporting_month": "January"}	2026-01-11 15:36:50.5162+02	2026-01-11 15:36:50.516218+02	f	1	3	3	13
350	{"fuel_type": "Gasoline", "distance_km": 1140, "vehicle_type": "Administrative Car", "co2e_emissions": 263.34, "reporting_year": 2023, "quantity_liters": 114, "reporting_month": "January"}	2026-01-11 15:36:50.520467+02	2026-01-11 15:36:50.520484+02	f	1	3	3	13
351	{"fuel_type": "Gasoline", "distance_km": 970, "vehicle_type": "Administrative Car", "co2e_emissions": 224.07, "reporting_year": 2023, "quantity_liters": 97, "reporting_month": "January"}	2026-01-11 15:36:50.524963+02	2026-01-11 15:36:50.524983+02	f	1	3	3	13
352	{"fuel_type": "Diesel", "distance_km": 1304, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 436.84, "reporting_year": 2023, "quantity_liters": 163, "reporting_month": "January"}	2026-01-11 15:36:50.52921+02	2026-01-11 15:36:50.529227+02	f	1	3	3	13
353	{"fuel_type": "Gasoline", "distance_km": 810, "vehicle_type": "Security Patrol", "co2e_emissions": 187.11, "reporting_year": 2023, "quantity_liters": 81, "reporting_month": "January"}	2026-01-11 15:36:50.533133+02	2026-01-11 15:36:50.533147+02	f	1	3	3	13
354	{"fuel_type": "Diesel", "distance_km": 6696, "vehicle_type": "Staff Bus", "co2e_emissions": 2243.16, "reporting_year": 2023, "quantity_liters": 837, "reporting_month": "February"}	2026-01-11 15:36:50.53863+02	2026-01-11 15:36:50.538644+02	f	1	3	3	13
355	{"fuel_type": "Diesel", "distance_km": 6552, "vehicle_type": "Staff Bus", "co2e_emissions": 2194.92, "reporting_year": 2023, "quantity_liters": 819, "reporting_month": "February"}	2026-01-11 15:36:50.545789+02	2026-01-11 15:36:50.545805+02	f	1	3	3	13
356	{"fuel_type": "Gasoline", "distance_km": 1290, "vehicle_type": "Administrative Car", "co2e_emissions": 297.99, "reporting_year": 2023, "quantity_liters": 129, "reporting_month": "February"}	2026-01-11 15:36:50.549658+02	2026-01-11 15:36:50.549672+02	f	1	3	3	13
357	{"fuel_type": "Gasoline", "distance_km": 970, "vehicle_type": "Administrative Car", "co2e_emissions": 224.07, "reporting_year": 2023, "quantity_liters": 97, "reporting_month": "February"}	2026-01-11 15:36:50.553381+02	2026-01-11 15:36:50.553395+02	f	1	3	3	13
358	{"fuel_type": "Diesel", "distance_km": 1592, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 533.32, "reporting_year": 2023, "quantity_liters": 199, "reporting_month": "February"}	2026-01-11 15:36:50.557477+02	2026-01-11 15:36:50.557493+02	f	1	3	3	13
359	{"fuel_type": "Gasoline", "distance_km": 890, "vehicle_type": "Security Patrol", "co2e_emissions": 205.59, "reporting_year": 2023, "quantity_liters": 89, "reporting_month": "February"}	2026-01-11 15:36:50.562002+02	2026-01-11 15:36:50.562017+02	f	1	3	3	13
360	{"fuel_type": "Diesel", "distance_km": 6824, "vehicle_type": "Staff Bus", "co2e_emissions": 2286.04, "reporting_year": 2023, "quantity_liters": 853, "reporting_month": "March"}	2026-01-11 15:36:50.565958+02	2026-01-11 15:36:50.565971+02	f	1	3	3	13
361	{"fuel_type": "Diesel", "distance_km": 6752, "vehicle_type": "Staff Bus", "co2e_emissions": 2261.92, "reporting_year": 2023, "quantity_liters": 844, "reporting_month": "March"}	2026-01-11 15:36:50.569289+02	2026-01-11 15:36:50.569303+02	f	1	3	3	13
362	{"fuel_type": "Gasoline", "distance_km": 1350, "vehicle_type": "Administrative Car", "co2e_emissions": 311.85, "reporting_year": 2023, "quantity_liters": 135, "reporting_month": "March"}	2026-01-11 15:36:50.572983+02	2026-01-11 15:36:50.573003+02	f	1	3	3	13
363	{"fuel_type": "Gasoline", "distance_km": 1090, "vehicle_type": "Administrative Car", "co2e_emissions": 251.79, "reporting_year": 2023, "quantity_liters": 109, "reporting_month": "March"}	2026-01-11 15:36:50.576652+02	2026-01-11 15:36:50.576667+02	f	1	3	3	13
364	{"fuel_type": "Diesel", "distance_km": 1408, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 471.68, "reporting_year": 2023, "quantity_liters": 176, "reporting_month": "March"}	2026-01-11 15:36:50.579972+02	2026-01-11 15:36:50.579986+02	f	1	3	3	13
365	{"fuel_type": "Gasoline", "distance_km": 850, "vehicle_type": "Security Patrol", "co2e_emissions": 196.35, "reporting_year": 2023, "quantity_liters": 85, "reporting_month": "March"}	2026-01-11 15:36:50.583486+02	2026-01-11 15:36:50.583499+02	f	1	3	3	13
366	{"fuel_type": "Diesel", "distance_km": 7224, "vehicle_type": "Staff Bus", "co2e_emissions": 2420.04, "reporting_year": 2023, "quantity_liters": 903, "reporting_month": "April"}	2026-01-11 15:36:50.586868+02	2026-01-11 15:36:50.586882+02	f	1	3	3	13
367	{"fuel_type": "Diesel", "distance_km": 6584, "vehicle_type": "Staff Bus", "co2e_emissions": 2205.64, "reporting_year": 2023, "quantity_liters": 823, "reporting_month": "April"}	2026-01-11 15:36:50.590593+02	2026-01-11 15:36:50.59061+02	f	1	3	3	13
368	{"fuel_type": "Gasoline", "distance_km": 1160, "vehicle_type": "Administrative Car", "co2e_emissions": 267.96, "reporting_year": 2023, "quantity_liters": 116, "reporting_month": "April"}	2026-01-11 15:36:50.594201+02	2026-01-11 15:36:50.594214+02	f	1	3	3	13
369	{"fuel_type": "Gasoline", "distance_km": 970, "vehicle_type": "Administrative Car", "co2e_emissions": 224.07, "reporting_year": 2023, "quantity_liters": 97, "reporting_month": "April"}	2026-01-11 15:36:50.597428+02	2026-01-11 15:36:50.597443+02	f	1	3	3	13
370	{"fuel_type": "Diesel", "distance_km": 1488, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 498.48, "reporting_year": 2023, "quantity_liters": 186, "reporting_month": "April"}	2026-01-11 15:36:50.602305+02	2026-01-11 15:36:50.602318+02	f	1	3	3	13
371	{"fuel_type": "Gasoline", "distance_km": 970, "vehicle_type": "Security Patrol", "co2e_emissions": 224.07, "reporting_year": 2023, "quantity_liters": 97, "reporting_month": "April"}	2026-01-11 15:36:50.606323+02	2026-01-11 15:36:50.60634+02	f	1	3	3	13
372	{"fuel_type": "Diesel", "distance_km": 5936, "vehicle_type": "Staff Bus", "co2e_emissions": 1988.56, "reporting_year": 2023, "quantity_liters": 742, "reporting_month": "May"}	2026-01-11 15:36:50.61028+02	2026-01-11 15:36:50.610294+02	f	1	3	3	13
373	{"fuel_type": "Diesel", "distance_km": 6072, "vehicle_type": "Staff Bus", "co2e_emissions": 2034.12, "reporting_year": 2023, "quantity_liters": 759, "reporting_month": "May"}	2026-01-11 15:36:50.61398+02	2026-01-11 15:36:50.613993+02	f	1	3	3	13
374	{"fuel_type": "Gasoline", "distance_km": 1020, "vehicle_type": "Administrative Car", "co2e_emissions": 235.62, "reporting_year": 2023, "quantity_liters": 102, "reporting_month": "May"}	2026-01-11 15:36:50.617648+02	2026-01-11 15:36:50.617662+02	f	1	3	3	13
375	{"fuel_type": "Gasoline", "distance_km": 850, "vehicle_type": "Administrative Car", "co2e_emissions": 196.35, "reporting_year": 2023, "quantity_liters": 85, "reporting_month": "May"}	2026-01-11 15:36:50.621831+02	2026-01-11 15:36:50.621846+02	f	1	3	3	13
376	{"fuel_type": "Diesel", "distance_km": 1408, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 471.68, "reporting_year": 2023, "quantity_liters": 176, "reporting_month": "May"}	2026-01-11 15:36:50.625599+02	2026-01-11 15:36:50.625613+02	f	1	3	3	13
377	{"fuel_type": "Gasoline", "distance_km": 810, "vehicle_type": "Security Patrol", "co2e_emissions": 187.11, "reporting_year": 2023, "quantity_liters": 81, "reporting_month": "May"}	2026-01-11 15:36:50.629342+02	2026-01-11 15:36:50.629353+02	f	1	3	3	13
378	{"fuel_type": "Diesel", "distance_km": 4528, "vehicle_type": "Staff Bus", "co2e_emissions": 1516.88, "reporting_year": 2023, "quantity_liters": 566, "reporting_month": "June"}	2026-01-11 15:36:50.632826+02	2026-01-11 15:36:50.63284+02	f	1	3	3	13
379	{"fuel_type": "Diesel", "distance_km": 4200, "vehicle_type": "Staff Bus", "co2e_emissions": 1407.0, "reporting_year": 2023, "quantity_liters": 525, "reporting_month": "June"}	2026-01-11 15:36:50.639792+02	2026-01-11 15:36:50.639808+02	f	1	3	3	13
380	{"fuel_type": "Gasoline", "distance_km": 890, "vehicle_type": "Administrative Car", "co2e_emissions": 205.59, "reporting_year": 2023, "quantity_liters": 89, "reporting_month": "June"}	2026-01-11 15:36:50.643562+02	2026-01-11 15:36:50.643575+02	f	1	3	3	13
381	{"fuel_type": "Gasoline", "distance_km": 670, "vehicle_type": "Administrative Car", "co2e_emissions": 154.77, "reporting_year": 2023, "quantity_liters": 67, "reporting_month": "June"}	2026-01-11 15:36:50.647549+02	2026-01-11 15:36:50.647565+02	f	1	3	3	13
382	{"fuel_type": "Diesel", "distance_km": 1000, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 335.0, "reporting_year": 2023, "quantity_liters": 125, "reporting_month": "June"}	2026-01-11 15:36:50.651749+02	2026-01-11 15:36:50.651768+02	f	1	3	3	13
383	{"fuel_type": "Gasoline", "distance_km": 680, "vehicle_type": "Security Patrol", "co2e_emissions": 157.08, "reporting_year": 2023, "quantity_liters": 68, "reporting_month": "June"}	2026-01-11 15:36:50.655439+02	2026-01-11 15:36:50.655454+02	f	1	3	3	13
384	{"fuel_type": "Diesel", "distance_km": 2568, "vehicle_type": "Staff Bus", "co2e_emissions": 860.28, "reporting_year": 2023, "quantity_liters": 321, "reporting_month": "July"}	2026-01-11 15:36:50.659106+02	2026-01-11 15:36:50.659119+02	f	1	3	3	13
385	{"fuel_type": "Diesel", "distance_km": 2360, "vehicle_type": "Staff Bus", "co2e_emissions": 790.6, "reporting_year": 2023, "quantity_liters": 295, "reporting_month": "July"}	2026-01-11 15:36:50.662378+02	2026-01-11 15:36:50.662391+02	f	1	3	3	13
386	{"fuel_type": "Gasoline", "distance_km": 520, "vehicle_type": "Administrative Car", "co2e_emissions": 120.12, "reporting_year": 2023, "quantity_liters": 52, "reporting_month": "July"}	2026-01-11 15:36:50.665778+02	2026-01-11 15:36:50.665793+02	f	1	3	3	13
387	{"fuel_type": "Gasoline", "distance_km": 410, "vehicle_type": "Administrative Car", "co2e_emissions": 94.71, "reporting_year": 2023, "quantity_liters": 41, "reporting_month": "July"}	2026-01-11 15:36:50.669823+02	2026-01-11 15:36:50.669839+02	f	1	3	3	13
388	{"fuel_type": "Diesel", "distance_km": 632, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 211.72, "reporting_year": 2023, "quantity_liters": 79, "reporting_month": "July"}	2026-01-11 15:36:50.673441+02	2026-01-11 15:36:50.673455+02	f	1	3	3	13
389	{"fuel_type": "Gasoline", "distance_km": 400, "vehicle_type": "Security Patrol", "co2e_emissions": 92.4, "reporting_year": 2023, "quantity_liters": 40, "reporting_month": "July"}	2026-01-11 15:36:50.676666+02	2026-01-11 15:36:50.676679+02	f	1	3	3	13
390	{"fuel_type": "Diesel", "distance_km": 1880, "vehicle_type": "Staff Bus", "co2e_emissions": 629.8, "reporting_year": 2023, "quantity_liters": 235, "reporting_month": "August"}	2026-01-11 15:36:50.680178+02	2026-01-11 15:36:50.680191+02	f	1	3	3	13
391	{"fuel_type": "Diesel", "distance_km": 1752, "vehicle_type": "Staff Bus", "co2e_emissions": 586.92, "reporting_year": 2023, "quantity_liters": 219, "reporting_month": "August"}	2026-01-11 15:36:50.68369+02	2026-01-11 15:36:50.683706+02	f	1	3	3	13
392	{"fuel_type": "Gasoline", "distance_km": 340, "vehicle_type": "Administrative Car", "co2e_emissions": 78.54, "reporting_year": 2023, "quantity_liters": 34, "reporting_month": "August"}	2026-01-11 15:36:50.688089+02	2026-01-11 15:36:50.688102+02	f	1	3	3	13
393	{"fuel_type": "Gasoline", "distance_km": 280, "vehicle_type": "Administrative Car", "co2e_emissions": 64.68, "reporting_year": 2023, "quantity_liters": 28, "reporting_month": "August"}	2026-01-11 15:36:50.693303+02	2026-01-11 15:36:50.693318+02	f	1	3	3	13
394	{"fuel_type": "Diesel", "distance_km": 464, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 155.44, "reporting_year": 2023, "quantity_liters": 58, "reporting_month": "August"}	2026-01-11 15:36:50.697581+02	2026-01-11 15:36:50.697602+02	f	1	3	3	13
395	{"fuel_type": "Gasoline", "distance_km": 290, "vehicle_type": "Security Patrol", "co2e_emissions": 66.99, "reporting_year": 2023, "quantity_liters": 29, "reporting_month": "August"}	2026-01-11 15:36:50.701908+02	2026-01-11 15:36:50.701924+02	f	1	3	3	13
396	{"fuel_type": "Diesel", "distance_km": 6680, "vehicle_type": "Staff Bus", "co2e_emissions": 2237.8, "reporting_year": 2023, "quantity_liters": 835, "reporting_month": "September"}	2026-01-11 15:36:50.705967+02	2026-01-11 15:36:50.705981+02	f	1	3	3	13
397	{"fuel_type": "Diesel", "distance_km": 5752, "vehicle_type": "Staff Bus", "co2e_emissions": 1926.92, "reporting_year": 2023, "quantity_liters": 719, "reporting_month": "September"}	2026-01-11 15:36:50.709819+02	2026-01-11 15:36:50.709833+02	f	1	3	3	13
398	{"fuel_type": "Gasoline", "distance_km": 1070, "vehicle_type": "Administrative Car", "co2e_emissions": 247.17, "reporting_year": 2023, "quantity_liters": 107, "reporting_month": "September"}	2026-01-11 15:36:50.714301+02	2026-01-11 15:36:50.714331+02	f	1	3	3	13
399	{"fuel_type": "Gasoline", "distance_km": 950, "vehicle_type": "Administrative Car", "co2e_emissions": 219.45, "reporting_year": 2023, "quantity_liters": 95, "reporting_month": "September"}	2026-01-11 15:36:50.718337+02	2026-01-11 15:36:50.718351+02	f	1	3	3	13
400	{"fuel_type": "Diesel", "distance_km": 1352, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 452.92, "reporting_year": 2023, "quantity_liters": 169, "reporting_month": "September"}	2026-01-11 15:36:50.722114+02	2026-01-11 15:36:50.722129+02	f	1	3	3	13
401	{"fuel_type": "Gasoline", "distance_km": 910, "vehicle_type": "Security Patrol", "co2e_emissions": 210.21, "reporting_year": 2023, "quantity_liters": 91, "reporting_month": "September"}	2026-01-11 15:36:50.725972+02	2026-01-11 15:36:50.725986+02	f	1	3	3	13
402	{"fuel_type": "Diesel", "distance_km": 6608, "vehicle_type": "Staff Bus", "co2e_emissions": 2213.68, "reporting_year": 2023, "quantity_liters": 826, "reporting_month": "October"}	2026-01-11 15:36:50.730438+02	2026-01-11 15:36:50.730453+02	f	1	3	3	13
403	{"fuel_type": "Diesel", "distance_km": 6232, "vehicle_type": "Staff Bus", "co2e_emissions": 2087.72, "reporting_year": 2023, "quantity_liters": 779, "reporting_month": "October"}	2026-01-11 15:36:50.736121+02	2026-01-11 15:36:50.736135+02	f	1	3	3	13
404	{"fuel_type": "Gasoline", "distance_km": 1250, "vehicle_type": "Administrative Car", "co2e_emissions": 288.75, "reporting_year": 2023, "quantity_liters": 125, "reporting_month": "October"}	2026-01-11 15:36:50.739821+02	2026-01-11 15:36:50.739836+02	f	1	3	3	13
405	{"fuel_type": "Gasoline", "distance_km": 980, "vehicle_type": "Administrative Car", "co2e_emissions": 226.38, "reporting_year": 2023, "quantity_liters": 98, "reporting_month": "October"}	2026-01-11 15:36:50.743385+02	2026-01-11 15:36:50.743399+02	f	1	3	3	13
406	{"fuel_type": "Diesel", "distance_km": 1480, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 495.8, "reporting_year": 2023, "quantity_liters": 185, "reporting_month": "October"}	2026-01-11 15:36:50.752103+02	2026-01-11 15:36:50.752119+02	f	1	3	3	13
407	{"fuel_type": "Gasoline", "distance_km": 1010, "vehicle_type": "Security Patrol", "co2e_emissions": 233.31, "reporting_year": 2023, "quantity_liters": 101, "reporting_month": "October"}	2026-01-11 15:36:50.755691+02	2026-01-11 15:36:50.755705+02	f	1	3	3	13
408	{"fuel_type": "Diesel", "distance_km": 6992, "vehicle_type": "Staff Bus", "co2e_emissions": 2342.32, "reporting_year": 2023, "quantity_liters": 874, "reporting_month": "November"}	2026-01-11 15:36:50.758824+02	2026-01-11 15:36:50.758835+02	f	1	3	3	13
409	{"fuel_type": "Diesel", "distance_km": 6272, "vehicle_type": "Staff Bus", "co2e_emissions": 2101.12, "reporting_year": 2023, "quantity_liters": 784, "reporting_month": "November"}	2026-01-11 15:36:50.762944+02	2026-01-11 15:36:50.762961+02	f	1	3	3	13
410	{"fuel_type": "Gasoline", "distance_km": 1350, "vehicle_type": "Administrative Car", "co2e_emissions": 311.85, "reporting_year": 2023, "quantity_liters": 135, "reporting_month": "November"}	2026-01-11 15:36:50.76695+02	2026-01-11 15:36:50.766965+02	f	1	3	3	13
411	{"fuel_type": "Gasoline", "distance_km": 1110, "vehicle_type": "Administrative Car", "co2e_emissions": 256.41, "reporting_year": 2023, "quantity_liters": 111, "reporting_month": "November"}	2026-01-11 15:36:50.77093+02	2026-01-11 15:36:50.770943+02	f	1	3	3	13
412	{"fuel_type": "Diesel", "distance_km": 1400, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 469.0, "reporting_year": 2023, "quantity_liters": 175, "reporting_month": "November"}	2026-01-11 15:36:50.774219+02	2026-01-11 15:36:50.774232+02	f	1	3	3	13
413	{"fuel_type": "Gasoline", "distance_km": 1010, "vehicle_type": "Security Patrol", "co2e_emissions": 233.31, "reporting_year": 2023, "quantity_liters": 101, "reporting_month": "November"}	2026-01-11 15:36:50.778202+02	2026-01-11 15:36:50.778218+02	f	1	3	3	13
414	{"fuel_type": "Diesel", "distance_km": 6080, "vehicle_type": "Staff Bus", "co2e_emissions": 2036.8, "reporting_year": 2023, "quantity_liters": 760, "reporting_month": "December"}	2026-01-11 15:36:50.782053+02	2026-01-11 15:36:50.782068+02	f	1	3	3	13
415	{"fuel_type": "Diesel", "distance_km": 5656, "vehicle_type": "Staff Bus", "co2e_emissions": 1894.76, "reporting_year": 2023, "quantity_liters": 707, "reporting_month": "December"}	2026-01-11 15:36:50.787212+02	2026-01-11 15:36:50.787225+02	f	1	3	3	13
416	{"fuel_type": "Gasoline", "distance_km": 950, "vehicle_type": "Administrative Car", "co2e_emissions": 219.45, "reporting_year": 2023, "quantity_liters": 95, "reporting_month": "December"}	2026-01-11 15:36:50.794377+02	2026-01-11 15:36:50.794395+02	f	1	3	3	13
417	{"fuel_type": "Gasoline", "distance_km": 840, "vehicle_type": "Administrative Car", "co2e_emissions": 194.04, "reporting_year": 2023, "quantity_liters": 84, "reporting_month": "December"}	2026-01-11 15:36:50.798489+02	2026-01-11 15:36:50.798504+02	f	1	3	3	13
418	{"fuel_type": "Diesel", "distance_km": 1160, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 388.6, "reporting_year": 2023, "quantity_liters": 145, "reporting_month": "December"}	2026-01-11 15:36:50.802349+02	2026-01-11 15:36:50.802363+02	f	1	3	3	13
419	{"fuel_type": "Gasoline", "distance_km": 820, "vehicle_type": "Security Patrol", "co2e_emissions": 189.42, "reporting_year": 2023, "quantity_liters": 82, "reporting_month": "December"}	2026-01-11 15:36:50.806315+02	2026-01-11 15:36:50.806332+02	f	1	3	3	13
420	{"fuel_type": "Diesel", "distance_km": 5968, "vehicle_type": "Staff Bus", "co2e_emissions": 1999.28, "reporting_year": 2024, "quantity_liters": 746, "reporting_month": "January"}	2026-01-11 15:36:50.811707+02	2026-01-11 15:36:50.811723+02	f	1	3	3	13
421	{"fuel_type": "Diesel", "distance_km": 5736, "vehicle_type": "Staff Bus", "co2e_emissions": 1921.56, "reporting_year": 2024, "quantity_liters": 717, "reporting_month": "January"}	2026-01-11 15:36:50.816888+02	2026-01-11 15:36:50.816902+02	f	1	3	3	13
422	{"fuel_type": "Gasoline", "distance_km": 1220, "vehicle_type": "Administrative Car", "co2e_emissions": 281.82, "reporting_year": 2024, "quantity_liters": 122, "reporting_month": "January"}	2026-01-11 15:36:50.82075+02	2026-01-11 15:36:50.820766+02	f	1	3	3	13
423	{"fuel_type": "Gasoline", "distance_km": 950, "vehicle_type": "Administrative Car", "co2e_emissions": 219.45, "reporting_year": 2024, "quantity_liters": 95, "reporting_month": "January"}	2026-01-11 15:36:50.824747+02	2026-01-11 15:36:50.824763+02	f	1	3	3	13
424	{"fuel_type": "Diesel", "distance_km": 1408, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 471.68, "reporting_year": 2024, "quantity_liters": 176, "reporting_month": "January"}	2026-01-11 15:36:50.82873+02	2026-01-11 15:36:50.828745+02	f	1	3	3	13
425	{"fuel_type": "Gasoline", "distance_km": 830, "vehicle_type": "Security Patrol", "co2e_emissions": 191.73, "reporting_year": 2024, "quantity_liters": 83, "reporting_month": "January"}	2026-01-11 15:36:50.833427+02	2026-01-11 15:36:50.83344+02	f	1	3	3	13
426	{"fuel_type": "Diesel", "distance_km": 6072, "vehicle_type": "Staff Bus", "co2e_emissions": 2034.12, "reporting_year": 2024, "quantity_liters": 759, "reporting_month": "February"}	2026-01-11 15:36:50.837002+02	2026-01-11 15:36:50.837018+02	f	1	3	3	13
427	{"fuel_type": "Diesel", "distance_km": 6320, "vehicle_type": "Staff Bus", "co2e_emissions": 2117.2, "reporting_year": 2024, "quantity_liters": 790, "reporting_month": "February"}	2026-01-11 15:36:50.840823+02	2026-01-11 15:36:50.840839+02	f	1	3	3	13
428	{"fuel_type": "Gasoline", "distance_km": 1160, "vehicle_type": "Administrative Car", "co2e_emissions": 267.96, "reporting_year": 2024, "quantity_liters": 116, "reporting_month": "February"}	2026-01-11 15:36:50.844396+02	2026-01-11 15:36:50.844407+02	f	1	3	3	13
429	{"fuel_type": "Gasoline", "distance_km": 1120, "vehicle_type": "Administrative Car", "co2e_emissions": 258.72, "reporting_year": 2024, "quantity_liters": 112, "reporting_month": "February"}	2026-01-11 15:36:50.847615+02	2026-01-11 15:36:50.847629+02	f	1	3	3	13
430	{"fuel_type": "Diesel", "distance_km": 1528, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 511.88, "reporting_year": 2024, "quantity_liters": 191, "reporting_month": "February"}	2026-01-11 15:36:50.851001+02	2026-01-11 15:36:50.851015+02	f	1	3	3	13
431	{"fuel_type": "Gasoline", "distance_km": 970, "vehicle_type": "Security Patrol", "co2e_emissions": 224.07, "reporting_year": 2024, "quantity_liters": 97, "reporting_month": "February"}	2026-01-11 15:36:50.854883+02	2026-01-11 15:36:50.854899+02	f	1	3	3	13
432	{"fuel_type": "Diesel", "distance_km": 6840, "vehicle_type": "Staff Bus", "co2e_emissions": 2291.4, "reporting_year": 2024, "quantity_liters": 855, "reporting_month": "March"}	2026-01-11 15:36:50.858676+02	2026-01-11 15:36:50.85869+02	f	1	3	3	13
433	{"fuel_type": "Diesel", "distance_km": 6176, "vehicle_type": "Staff Bus", "co2e_emissions": 2068.96, "reporting_year": 2024, "quantity_liters": 772, "reporting_month": "March"}	2026-01-11 15:36:50.862289+02	2026-01-11 15:36:50.862301+02	f	1	3	3	13
434	{"fuel_type": "Gasoline", "distance_km": 1350, "vehicle_type": "Administrative Car", "co2e_emissions": 311.85, "reporting_year": 2024, "quantity_liters": 135, "reporting_month": "March"}	2026-01-11 15:36:50.865824+02	2026-01-11 15:36:50.865855+02	f	1	3	3	13
435	{"fuel_type": "Gasoline", "distance_km": 980, "vehicle_type": "Administrative Car", "co2e_emissions": 226.38, "reporting_year": 2024, "quantity_liters": 98, "reporting_month": "March"}	2026-01-11 15:36:50.872317+02	2026-01-11 15:36:50.872333+02	f	1	3	3	13
436	{"fuel_type": "Diesel", "distance_km": 1440, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 482.4, "reporting_year": 2024, "quantity_liters": 180, "reporting_month": "March"}	2026-01-11 15:36:50.87615+02	2026-01-11 15:36:50.876161+02	f	1	3	3	13
437	{"fuel_type": "Gasoline", "distance_km": 920, "vehicle_type": "Security Patrol", "co2e_emissions": 212.52, "reporting_year": 2024, "quantity_liters": 92, "reporting_month": "March"}	2026-01-11 15:36:50.879679+02	2026-01-11 15:36:50.879692+02	f	1	3	3	13
438	{"fuel_type": "Diesel", "distance_km": 7152, "vehicle_type": "Staff Bus", "co2e_emissions": 2395.92, "reporting_year": 2024, "quantity_liters": 894, "reporting_month": "April"}	2026-01-11 15:36:50.885157+02	2026-01-11 15:36:50.885174+02	f	1	3	3	13
439	{"fuel_type": "Diesel", "distance_km": 5824, "vehicle_type": "Staff Bus", "co2e_emissions": 1951.04, "reporting_year": 2024, "quantity_liters": 728, "reporting_month": "April"}	2026-01-11 15:36:50.889258+02	2026-01-11 15:36:50.889272+02	f	1	3	3	13
440	{"fuel_type": "Gasoline", "distance_km": 1210, "vehicle_type": "Administrative Car", "co2e_emissions": 279.51, "reporting_year": 2024, "quantity_liters": 121, "reporting_month": "April"}	2026-01-11 15:36:50.89289+02	2026-01-11 15:36:50.892904+02	f	1	3	3	13
441	{"fuel_type": "Gasoline", "distance_km": 1130, "vehicle_type": "Administrative Car", "co2e_emissions": 261.03, "reporting_year": 2024, "quantity_liters": 113, "reporting_month": "April"}	2026-01-11 15:36:50.896728+02	2026-01-11 15:36:50.896741+02	f	1	3	3	13
442	{"fuel_type": "Diesel", "distance_km": 1584, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 530.64, "reporting_year": 2024, "quantity_liters": 198, "reporting_month": "April"}	2026-01-11 15:36:50.901936+02	2026-01-11 15:36:50.901953+02	f	1	3	3	13
443	{"fuel_type": "Gasoline", "distance_km": 850, "vehicle_type": "Security Patrol", "co2e_emissions": 196.35, "reporting_year": 2024, "quantity_liters": 85, "reporting_month": "April"}	2026-01-11 15:36:50.905911+02	2026-01-11 15:36:50.905924+02	f	1	3	3	13
444	{"fuel_type": "Diesel", "distance_km": 5816, "vehicle_type": "Staff Bus", "co2e_emissions": 1948.36, "reporting_year": 2024, "quantity_liters": 727, "reporting_month": "May"}	2026-01-11 15:36:50.909432+02	2026-01-11 15:36:50.909445+02	f	1	3	3	13
445	{"fuel_type": "Diesel", "distance_km": 5104, "vehicle_type": "Staff Bus", "co2e_emissions": 1709.84, "reporting_year": 2024, "quantity_liters": 638, "reporting_month": "May"}	2026-01-11 15:36:50.913297+02	2026-01-11 15:36:50.913311+02	f	1	3	3	13
446	{"fuel_type": "Gasoline", "distance_km": 1190, "vehicle_type": "Administrative Car", "co2e_emissions": 274.89, "reporting_year": 2024, "quantity_liters": 119, "reporting_month": "May"}	2026-01-11 15:36:50.917266+02	2026-01-11 15:36:50.917281+02	f	1	3	3	13
447	{"fuel_type": "Gasoline", "distance_km": 1010, "vehicle_type": "Administrative Car", "co2e_emissions": 233.31, "reporting_year": 2024, "quantity_liters": 101, "reporting_month": "May"}	2026-01-11 15:36:50.921069+02	2026-01-11 15:36:50.921081+02	f	1	3	3	13
448	{"fuel_type": "Diesel", "distance_km": 1408, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 471.68, "reporting_year": 2024, "quantity_liters": 176, "reporting_month": "May"}	2026-01-11 15:36:50.9244+02	2026-01-11 15:36:50.924411+02	f	1	3	3	13
449	{"fuel_type": "Gasoline", "distance_km": 880, "vehicle_type": "Security Patrol", "co2e_emissions": 203.28, "reporting_year": 2024, "quantity_liters": 88, "reporting_month": "May"}	2026-01-11 15:36:50.927617+02	2026-01-11 15:36:50.927632+02	f	1	3	3	13
450	{"fuel_type": "Diesel", "distance_km": 4800, "vehicle_type": "Staff Bus", "co2e_emissions": 1608.0, "reporting_year": 2024, "quantity_liters": 600, "reporting_month": "June"}	2026-01-11 15:36:50.931252+02	2026-01-11 15:36:50.931269+02	f	1	3	3	13
451	{"fuel_type": "Diesel", "distance_km": 4144, "vehicle_type": "Staff Bus", "co2e_emissions": 1388.24, "reporting_year": 2024, "quantity_liters": 518, "reporting_month": "June"}	2026-01-11 15:36:50.934809+02	2026-01-11 15:36:50.934824+02	f	1	3	3	13
452	{"fuel_type": "Gasoline", "distance_km": 830, "vehicle_type": "Administrative Car", "co2e_emissions": 191.73, "reporting_year": 2024, "quantity_liters": 83, "reporting_month": "June"}	2026-01-11 15:36:50.938646+02	2026-01-11 15:36:50.938661+02	f	1	3	3	13
453	{"fuel_type": "Gasoline", "distance_km": 690, "vehicle_type": "Administrative Car", "co2e_emissions": 159.39, "reporting_year": 2024, "quantity_liters": 69, "reporting_month": "June"}	2026-01-11 15:36:50.942155+02	2026-01-11 15:36:50.942168+02	f	1	3	3	13
454	{"fuel_type": "Diesel", "distance_km": 1056, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 353.76, "reporting_year": 2024, "quantity_liters": 132, "reporting_month": "June"}	2026-01-11 15:36:50.945585+02	2026-01-11 15:36:50.945605+02	f	1	3	3	13
455	{"fuel_type": "Gasoline", "distance_km": 600, "vehicle_type": "Security Patrol", "co2e_emissions": 138.6, "reporting_year": 2024, "quantity_liters": 60, "reporting_month": "June"}	2026-01-11 15:36:50.949506+02	2026-01-11 15:36:50.949523+02	f	1	3	3	13
456	{"fuel_type": "Diesel", "distance_km": 2440, "vehicle_type": "Staff Bus", "co2e_emissions": 817.4, "reporting_year": 2024, "quantity_liters": 305, "reporting_month": "July"}	2026-01-11 15:36:50.953402+02	2026-01-11 15:36:50.953417+02	f	1	3	3	13
457	{"fuel_type": "Diesel", "distance_km": 2560, "vehicle_type": "Staff Bus", "co2e_emissions": 857.6, "reporting_year": 2024, "quantity_liters": 320, "reporting_month": "July"}	2026-01-11 15:36:50.958376+02	2026-01-11 15:36:50.958389+02	f	1	3	3	13
458	{"fuel_type": "Gasoline", "distance_km": 530, "vehicle_type": "Administrative Car", "co2e_emissions": 122.43, "reporting_year": 2024, "quantity_liters": 53, "reporting_month": "July"}	2026-01-11 15:36:50.962809+02	2026-01-11 15:36:50.962827+02	f	1	3	3	13
459	{"fuel_type": "Gasoline", "distance_km": 390, "vehicle_type": "Administrative Car", "co2e_emissions": 90.09, "reporting_year": 2024, "quantity_liters": 39, "reporting_month": "July"}	2026-01-11 15:36:50.966907+02	2026-01-11 15:36:50.966923+02	f	1	3	3	13
460	{"fuel_type": "Diesel", "distance_km": 544, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 182.24, "reporting_year": 2024, "quantity_liters": 68, "reporting_month": "July"}	2026-01-11 15:36:50.97077+02	2026-01-11 15:36:50.970782+02	f	1	3	3	13
461	{"fuel_type": "Gasoline", "distance_km": 360, "vehicle_type": "Security Patrol", "co2e_emissions": 83.16, "reporting_year": 2024, "quantity_liters": 36, "reporting_month": "July"}	2026-01-11 15:36:50.975444+02	2026-01-11 15:36:50.975458+02	f	1	3	3	13
462	{"fuel_type": "Diesel", "distance_km": 2184, "vehicle_type": "Staff Bus", "co2e_emissions": 731.64, "reporting_year": 2024, "quantity_liters": 273, "reporting_month": "August"}	2026-01-11 15:36:50.980645+02	2026-01-11 15:36:50.98066+02	f	1	3	3	13
463	{"fuel_type": "Diesel", "distance_km": 1880, "vehicle_type": "Staff Bus", "co2e_emissions": 629.8, "reporting_year": 2024, "quantity_liters": 235, "reporting_month": "August"}	2026-01-11 15:36:50.984304+02	2026-01-11 15:36:50.984319+02	f	1	3	3	13
464	{"fuel_type": "Gasoline", "distance_km": 380, "vehicle_type": "Administrative Car", "co2e_emissions": 87.78, "reporting_year": 2024, "quantity_liters": 38, "reporting_month": "August"}	2026-01-11 15:36:50.988736+02	2026-01-11 15:36:50.988752+02	f	1	3	3	13
465	{"fuel_type": "Gasoline", "distance_km": 280, "vehicle_type": "Administrative Car", "co2e_emissions": 64.68, "reporting_year": 2024, "quantity_liters": 28, "reporting_month": "August"}	2026-01-11 15:36:50.993052+02	2026-01-11 15:36:50.993076+02	f	1	3	3	13
466	{"fuel_type": "Diesel", "distance_km": 432, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 144.72, "reporting_year": 2024, "quantity_liters": 54, "reporting_month": "August"}	2026-01-11 15:36:51.000776+02	2026-01-11 15:36:51.000797+02	f	1	3	3	13
467	{"fuel_type": "Gasoline", "distance_km": 290, "vehicle_type": "Security Patrol", "co2e_emissions": 66.99, "reporting_year": 2024, "quantity_liters": 29, "reporting_month": "August"}	2026-01-11 15:36:51.006069+02	2026-01-11 15:36:51.006084+02	f	1	3	3	13
468	{"fuel_type": "Diesel", "distance_km": 5944, "vehicle_type": "Staff Bus", "co2e_emissions": 1991.24, "reporting_year": 2024, "quantity_liters": 743, "reporting_month": "September"}	2026-01-11 15:36:51.010511+02	2026-01-11 15:36:51.010528+02	f	1	3	3	13
469	{"fuel_type": "Diesel", "distance_km": 5696, "vehicle_type": "Staff Bus", "co2e_emissions": 1908.16, "reporting_year": 2024, "quantity_liters": 712, "reporting_month": "September"}	2026-01-11 15:36:51.014389+02	2026-01-11 15:36:51.014404+02	f	1	3	3	13
470	{"fuel_type": "Gasoline", "distance_km": 1250, "vehicle_type": "Administrative Car", "co2e_emissions": 288.75, "reporting_year": 2024, "quantity_liters": 125, "reporting_month": "September"}	2026-01-11 15:36:51.017933+02	2026-01-11 15:36:51.017949+02	f	1	3	3	13
471	{"fuel_type": "Gasoline", "distance_km": 900, "vehicle_type": "Administrative Car", "co2e_emissions": 207.9, "reporting_year": 2024, "quantity_liters": 90, "reporting_month": "September"}	2026-01-11 15:36:51.02163+02	2026-01-11 15:36:51.021653+02	f	1	3	3	13
472	{"fuel_type": "Diesel", "distance_km": 1520, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 509.2, "reporting_year": 2024, "quantity_liters": 190, "reporting_month": "September"}	2026-01-11 15:36:51.025695+02	2026-01-11 15:36:51.025711+02	f	1	3	3	13
473	{"fuel_type": "Gasoline", "distance_km": 960, "vehicle_type": "Security Patrol", "co2e_emissions": 221.76, "reporting_year": 2024, "quantity_liters": 96, "reporting_month": "September"}	2026-01-11 15:36:51.029208+02	2026-01-11 15:36:51.029224+02	f	1	3	3	13
474	{"fuel_type": "Diesel", "distance_km": 6672, "vehicle_type": "Staff Bus", "co2e_emissions": 2235.12, "reporting_year": 2024, "quantity_liters": 834, "reporting_month": "October"}	2026-01-11 15:36:51.032518+02	2026-01-11 15:36:51.032533+02	f	1	3	3	13
475	{"fuel_type": "Diesel", "distance_km": 5768, "vehicle_type": "Staff Bus", "co2e_emissions": 1932.28, "reporting_year": 2024, "quantity_liters": 721, "reporting_month": "October"}	2026-01-11 15:36:51.035761+02	2026-01-11 15:36:51.035775+02	f	1	3	3	13
476	{"fuel_type": "Gasoline", "distance_km": 1310, "vehicle_type": "Administrative Car", "co2e_emissions": 302.61, "reporting_year": 2024, "quantity_liters": 131, "reporting_month": "October"}	2026-01-11 15:36:51.039688+02	2026-01-11 15:36:51.039705+02	f	1	3	3	13
477	{"fuel_type": "Gasoline", "distance_km": 1080, "vehicle_type": "Administrative Car", "co2e_emissions": 249.48, "reporting_year": 2024, "quantity_liters": 108, "reporting_month": "October"}	2026-01-11 15:36:51.046313+02	2026-01-11 15:36:51.046329+02	f	1	3	3	13
478	{"fuel_type": "Diesel", "distance_km": 1520, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 509.2, "reporting_year": 2024, "quantity_liters": 190, "reporting_month": "October"}	2026-01-11 15:36:51.050406+02	2026-01-11 15:36:51.050419+02	f	1	3	3	13
479	{"fuel_type": "Gasoline", "distance_km": 890, "vehicle_type": "Security Patrol", "co2e_emissions": 205.59, "reporting_year": 2024, "quantity_liters": 89, "reporting_month": "October"}	2026-01-11 15:36:51.053975+02	2026-01-11 15:36:51.05399+02	f	1	3	3	13
480	{"fuel_type": "Diesel", "distance_km": 6000, "vehicle_type": "Staff Bus", "co2e_emissions": 2010.0, "reporting_year": 2024, "quantity_liters": 750, "reporting_month": "November"}	2026-01-11 15:36:51.061274+02	2026-01-11 15:36:51.061291+02	f	1	3	3	13
481	{"fuel_type": "Diesel", "distance_km": 6064, "vehicle_type": "Staff Bus", "co2e_emissions": 2031.44, "reporting_year": 2024, "quantity_liters": 758, "reporting_month": "November"}	2026-01-11 15:36:51.066527+02	2026-01-11 15:36:51.066542+02	f	1	3	3	13
482	{"fuel_type": "Gasoline", "distance_km": 1330, "vehicle_type": "Administrative Car", "co2e_emissions": 307.23, "reporting_year": 2024, "quantity_liters": 133, "reporting_month": "November"}	2026-01-11 15:36:51.070498+02	2026-01-11 15:36:51.070515+02	f	1	3	3	13
483	{"fuel_type": "Gasoline", "distance_km": 1080, "vehicle_type": "Administrative Car", "co2e_emissions": 249.48, "reporting_year": 2024, "quantity_liters": 108, "reporting_month": "November"}	2026-01-11 15:36:51.074491+02	2026-01-11 15:36:51.074506+02	f	1	3	3	13
484	{"fuel_type": "Diesel", "distance_km": 1568, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 525.28, "reporting_year": 2024, "quantity_liters": 196, "reporting_month": "November"}	2026-01-11 15:36:51.078149+02	2026-01-11 15:36:51.078162+02	f	1	3	3	13
485	{"fuel_type": "Gasoline", "distance_km": 910, "vehicle_type": "Security Patrol", "co2e_emissions": 210.21, "reporting_year": 2024, "quantity_liters": 91, "reporting_month": "November"}	2026-01-11 15:36:51.083126+02	2026-01-11 15:36:51.08314+02	f	1	3	3	13
486	{"fuel_type": "Diesel", "distance_km": 5920, "vehicle_type": "Staff Bus", "co2e_emissions": 1983.2, "reporting_year": 2024, "quantity_liters": 740, "reporting_month": "December"}	2026-01-11 15:36:51.086985+02	2026-01-11 15:36:51.087002+02	f	1	3	3	13
487	{"fuel_type": "Diesel", "distance_km": 4960, "vehicle_type": "Staff Bus", "co2e_emissions": 1661.6, "reporting_year": 2024, "quantity_liters": 620, "reporting_month": "December"}	2026-01-11 15:36:51.090833+02	2026-01-11 15:36:51.090848+02	f	1	3	3	13
488	{"fuel_type": "Gasoline", "distance_km": 1120, "vehicle_type": "Administrative Car", "co2e_emissions": 258.72, "reporting_year": 2024, "quantity_liters": 112, "reporting_month": "December"}	2026-01-11 15:36:51.094332+02	2026-01-11 15:36:51.094343+02	f	1	3	3	13
489	{"fuel_type": "Gasoline", "distance_km": 910, "vehicle_type": "Administrative Car", "co2e_emissions": 210.21, "reporting_year": 2024, "quantity_liters": 91, "reporting_month": "December"}	2026-01-11 15:36:51.099018+02	2026-01-11 15:36:51.09903+02	f	1	3	3	13
490	{"fuel_type": "Diesel", "distance_km": 1160, "vehicle_type": "Maintenance Vehicle", "co2e_emissions": 388.6, "reporting_year": 2024, "quantity_liters": 145, "reporting_month": "December"}	2026-01-11 15:36:51.102877+02	2026-01-11 15:36:51.102893+02	f	1	3	3	13
491	{"fuel_type": "Gasoline", "distance_km": 750, "vehicle_type": "Security Patrol", "co2e_emissions": 173.25, "reporting_year": 2024, "quantity_liters": 75, "reporting_month": "December"}	2026-01-11 15:36:51.107756+02	2026-01-11 15:36:51.107771+02	f	1	3	3	13
492	{"co2e_emissions": 46980.0, "equipment_type": "Split AC Units", "reporting_year": 2020, "leakage_rate_pct": 5.0, "refrigerant_type": "R-410A", "initial_charge_kg": 450, "quantity_leaked_kg": 22.5}	2026-01-11 15:36:51.160638+02	2026-01-11 15:36:51.160652+02	f	1	3	3	14
493	{"co2e_emissions": 12012.0, "equipment_type": "Central Chiller", "reporting_year": 2020, "leakage_rate_pct": 3.0, "refrigerant_type": "R-134a", "initial_charge_kg": 280, "quantity_leaked_kg": 8.4}	2026-01-11 15:36:51.164726+02	2026-01-11 15:36:51.164747+02	f	1	3	3	14
494	{"co2e_emissions": 15033.6, "equipment_type": "VRF System", "reporting_year": 2020, "leakage_rate_pct": 4.0, "refrigerant_type": "R-410A", "initial_charge_kg": 180, "quantity_leaked_kg": 7.2}	2026-01-11 15:36:51.168792+02	2026-01-11 15:36:51.168808+02	f	1	3	3	14
495	{"co2e_emissions": 715.0, "equipment_type": "Refrigerators", "reporting_year": 2020, "leakage_rate_pct": 2.0, "refrigerant_type": "R-134a", "initial_charge_kg": 25, "quantity_leaked_kg": 0.5}	2026-01-11 15:36:51.172205+02	2026-01-11 15:36:51.17222+02	f	1	3	3	14
496	{"co2e_emissions": 46040.4, "equipment_type": "Split AC Units", "reporting_year": 2021, "leakage_rate_pct": 4.9, "refrigerant_type": "R-410A", "initial_charge_kg": 450, "quantity_leaked_kg": 22.05}	2026-01-11 15:36:51.175715+02	2026-01-11 15:36:51.175729+02	f	1	3	3	14
497	{"co2e_emissions": 11771.76, "equipment_type": "Central Chiller", "reporting_year": 2021, "leakage_rate_pct": 2.94, "refrigerant_type": "R-134a", "initial_charge_kg": 280, "quantity_leaked_kg": 8.23}	2026-01-11 15:36:51.179573+02	2026-01-11 15:36:51.179592+02	f	1	3	3	14
498	{"co2e_emissions": 14732.93, "equipment_type": "VRF System", "reporting_year": 2021, "leakage_rate_pct": 3.92, "refrigerant_type": "R-410A", "initial_charge_kg": 180, "quantity_leaked_kg": 7.06}	2026-01-11 15:36:51.183232+02	2026-01-11 15:36:51.183249+02	f	1	3	3	14
499	{"co2e_emissions": 700.7, "equipment_type": "Refrigerators", "reporting_year": 2021, "leakage_rate_pct": 1.96, "refrigerant_type": "R-134a", "initial_charge_kg": 25, "quantity_leaked_kg": 0.49}	2026-01-11 15:36:51.186586+02	2026-01-11 15:36:51.186601+02	f	1	3	3	14
500	{"co2e_emissions": 45100.8, "equipment_type": "Split AC Units", "reporting_year": 2022, "leakage_rate_pct": 4.8, "refrigerant_type": "R-410A", "initial_charge_kg": 450, "quantity_leaked_kg": 21.6}	2026-01-11 15:36:51.190155+02	2026-01-11 15:36:51.190168+02	f	1	3	3	14
501	{"co2e_emissions": 11531.52, "equipment_type": "Central Chiller", "reporting_year": 2022, "leakage_rate_pct": 2.88, "refrigerant_type": "R-134a", "initial_charge_kg": 280, "quantity_leaked_kg": 8.06}	2026-01-11 15:36:51.195718+02	2026-01-11 15:36:51.195734+02	f	1	3	3	14
502	{"co2e_emissions": 14432.26, "equipment_type": "VRF System", "reporting_year": 2022, "leakage_rate_pct": 3.84, "refrigerant_type": "R-410A", "initial_charge_kg": 180, "quantity_leaked_kg": 6.91}	2026-01-11 15:36:51.199055+02	2026-01-11 15:36:51.19907+02	f	1	3	3	14
503	{"co2e_emissions": 686.4, "equipment_type": "Refrigerators", "reporting_year": 2022, "leakage_rate_pct": 1.92, "refrigerant_type": "R-134a", "initial_charge_kg": 25, "quantity_leaked_kg": 0.48}	2026-01-11 15:36:51.203126+02	2026-01-11 15:36:51.203144+02	f	1	3	3	14
504	{"co2e_emissions": 44161.2, "equipment_type": "Split AC Units", "reporting_year": 2023, "leakage_rate_pct": 4.7, "refrigerant_type": "R-410A", "initial_charge_kg": 450, "quantity_leaked_kg": 21.15}	2026-01-11 15:36:51.207854+02	2026-01-11 15:36:51.207872+02	f	1	3	3	14
505	{"co2e_emissions": 11291.28, "equipment_type": "Central Chiller", "reporting_year": 2023, "leakage_rate_pct": 2.82, "refrigerant_type": "R-134a", "initial_charge_kg": 280, "quantity_leaked_kg": 7.9}	2026-01-11 15:36:51.2158+02	2026-01-11 15:36:51.215817+02	f	1	3	3	14
506	{"co2e_emissions": 14131.58, "equipment_type": "VRF System", "reporting_year": 2023, "leakage_rate_pct": 3.76, "refrigerant_type": "R-410A", "initial_charge_kg": 180, "quantity_leaked_kg": 6.77}	2026-01-11 15:36:51.220411+02	2026-01-11 15:36:51.220427+02	f	1	3	3	14
507	{"co2e_emissions": 672.1, "equipment_type": "Refrigerators", "reporting_year": 2023, "leakage_rate_pct": 1.88, "refrigerant_type": "R-134a", "initial_charge_kg": 25, "quantity_leaked_kg": 0.47}	2026-01-11 15:36:51.224131+02	2026-01-11 15:36:51.224147+02	f	1	3	3	14
508	{"co2e_emissions": 43221.6, "equipment_type": "Split AC Units", "reporting_year": 2024, "leakage_rate_pct": 4.6, "refrigerant_type": "R-410A", "initial_charge_kg": 450, "quantity_leaked_kg": 20.7}	2026-01-11 15:36:51.227751+02	2026-01-11 15:36:51.227782+02	f	1	3	3	14
509	{"co2e_emissions": 11051.04, "equipment_type": "Central Chiller", "reporting_year": 2024, "leakage_rate_pct": 2.76, "refrigerant_type": "R-134a", "initial_charge_kg": 280, "quantity_leaked_kg": 7.73}	2026-01-11 15:36:51.231419+02	2026-01-11 15:36:51.231435+02	f	1	3	3	14
510	{"co2e_emissions": 13830.91, "equipment_type": "VRF System", "reporting_year": 2024, "leakage_rate_pct": 3.68, "refrigerant_type": "R-410A", "initial_charge_kg": 180, "quantity_leaked_kg": 6.62}	2026-01-11 15:36:51.235067+02	2026-01-11 15:36:51.235087+02	f	1	3	3	14
511	{"co2e_emissions": 657.8, "equipment_type": "Refrigerators", "reporting_year": 2024, "leakage_rate_pct": 1.84, "refrigerant_type": "R-134a", "initial_charge_kg": 25, "quantity_leaked_kg": 0.46}	2026-01-11 15:36:51.239655+02	2026-01-11 15:36:51.239672+02	f	1	3	3	14
512	{"location": "Server Room", "system_type": "CO2", "co2e_emissions": 7.02, "reporting_year": 2020, "quantity_released_kg": 7.02}	2026-01-11 15:36:51.272019+02	2026-01-11 15:36:51.272036+02	f	1	3	3	15
513	{"location": "Server Room", "system_type": "CO2", "co2e_emissions": 10.2, "reporting_year": 2021, "quantity_released_kg": 10.2}	2026-01-11 15:36:51.275738+02	2026-01-11 15:36:51.275754+02	f	1	3	3	15
514	{"location": "Server Room", "system_type": "CO2", "co2e_emissions": 13.24, "reporting_year": 2022, "quantity_released_kg": 13.24}	2026-01-11 15:36:51.279141+02	2026-01-11 15:36:51.279155+02	f	1	3	3	15
515	{"location": "Server Room", "system_type": "CO2", "co2e_emissions": 10.2, "reporting_year": 2023, "quantity_released_kg": 10.2}	2026-01-11 15:36:51.282594+02	2026-01-11 15:36:51.282609+02	f	1	3	3	15
516	{"location": "Server Room", "system_type": "CO2", "co2e_emissions": 6.53, "reporting_year": 2024, "quantity_released_kg": 6.53}	2026-01-11 15:36:51.291367+02	2026-01-11 15:36:51.291383+02	f	1	3	3	15
517	{"building": "Building 401", "co2e_emissions": 59147.55, "reporting_year": 2020, "consumption_kwh": 119490, "reporting_month": "January", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.377928+02	2026-01-11 15:36:51.377939+02	f	1	3	3	16
518	{"building": "Building 2401", "co2e_emissions": 60700.86, "reporting_year": 2020, "consumption_kwh": 122628, "reporting_month": "January", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.381446+02	2026-01-11 15:36:51.381463+02	f	1	3	3	16
519	{"building": "Building 2401-1", "co2e_emissions": 1669.57, "consumption_tr": 11130.45, "reporting_year": 2020, "reporting_month": "January"}	2026-01-11 15:36:51.385364+02	2026-01-11 15:36:51.38538+02	f	1	3	3	17
520	{"building": "Building 2401-2", "co2e_emissions": 1393.22, "consumption_tr": 9288.12, "reporting_year": 2020, "reporting_month": "January"}	2026-01-11 15:36:51.388829+02	2026-01-11 15:36:51.388842+02	f	1	3	3	17
521	{"building": "Building 401", "co2e_emissions": 52569.99, "reporting_year": 2020, "consumption_kwh": 106202, "reporting_month": "February", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.392074+02	2026-01-11 15:36:51.392087+02	f	1	3	3	16
522	{"building": "Building 2401", "co2e_emissions": 52339.82, "reporting_year": 2020, "consumption_kwh": 105737, "reporting_month": "February", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.395294+02	2026-01-11 15:36:51.39531+02	f	1	3	3	16
523	{"building": "Building 2401-1", "co2e_emissions": 1130.63, "consumption_tr": 7537.52, "reporting_year": 2020, "reporting_month": "February"}	2026-01-11 15:36:51.40142+02	2026-01-11 15:36:51.401436+02	f	1	3	3	17
524	{"building": "Building 2401-2", "co2e_emissions": 1360.27, "consumption_tr": 9068.44, "reporting_year": 2020, "reporting_month": "February"}	2026-01-11 15:36:51.405075+02	2026-01-11 15:36:51.405089+02	f	1	3	3	17
525	{"building": "Building 401", "co2e_emissions": 48519.9, "reporting_year": 2020, "consumption_kwh": 98020, "reporting_month": "March", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.408313+02	2026-01-11 15:36:51.408327+02	f	1	3	3	16
526	{"building": "Building 2401", "co2e_emissions": 45213.3, "reporting_year": 2020, "consumption_kwh": 91340, "reporting_month": "March", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.411668+02	2026-01-11 15:36:51.411685+02	f	1	3	3	16
527	{"building": "Building 2401-1", "co2e_emissions": 7223.26, "consumption_tr": 48155.09, "reporting_year": 2020, "reporting_month": "March"}	2026-01-11 15:36:51.415331+02	2026-01-11 15:36:51.415346+02	f	1	3	3	17
528	{"building": "Building 2401-2", "co2e_emissions": 7135.96, "consumption_tr": 47573.04, "reporting_year": 2020, "reporting_month": "March"}	2026-01-11 15:36:51.42151+02	2026-01-11 15:36:51.421528+02	f	1	3	3	17
529	{"building": "Building 401", "co2e_emissions": 56992.32, "reporting_year": 2020, "consumption_kwh": 115136, "reporting_month": "April", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.425653+02	2026-01-11 15:36:51.425669+02	f	1	3	3	16
530	{"building": "Building 2401", "co2e_emissions": 54590.58, "reporting_year": 2020, "consumption_kwh": 110284, "reporting_month": "April", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.429804+02	2026-01-11 15:36:51.429829+02	f	1	3	3	16
531	{"building": "Building 2401-1", "co2e_emissions": 5903.48, "consumption_tr": 39356.55, "reporting_year": 2020, "reporting_month": "April"}	2026-01-11 15:36:51.43383+02	2026-01-11 15:36:51.433847+02	f	1	3	3	17
532	{"building": "Building 2401-2", "co2e_emissions": 6665.55, "consumption_tr": 44436.97, "reporting_year": 2020, "reporting_month": "April"}	2026-01-11 15:36:51.437651+02	2026-01-11 15:36:51.437668+02	f	1	3	3	17
533	{"building": "Building 401", "co2e_emissions": 50952.82, "reporting_year": 2020, "consumption_kwh": 102935, "reporting_month": "May", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.441687+02	2026-01-11 15:36:51.44171+02	f	1	3	3	16
534	{"building": "Building 2401", "co2e_emissions": 49872.24, "reporting_year": 2020, "consumption_kwh": 100752, "reporting_month": "May", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.446296+02	2026-01-11 15:36:51.446313+02	f	1	3	3	16
535	{"building": "Building 2401-1", "co2e_emissions": 13229.18, "consumption_tr": 88194.52, "reporting_year": 2020, "reporting_month": "May"}	2026-01-11 15:36:51.450314+02	2026-01-11 15:36:51.450332+02	f	1	3	3	17
536	{"building": "Building 2401-2", "co2e_emissions": 15952.64, "consumption_tr": 106350.96, "reporting_year": 2020, "reporting_month": "May"}	2026-01-11 15:36:51.454488+02	2026-01-11 15:36:51.454504+02	f	1	3	3	17
537	{"building": "Building 401", "co2e_emissions": 56009.25, "reporting_year": 2020, "consumption_kwh": 113150, "reporting_month": "June", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.461238+02	2026-01-11 15:36:51.461255+02	f	1	3	3	16
538	{"building": "Building 2401", "co2e_emissions": 54844.02, "reporting_year": 2020, "consumption_kwh": 110796, "reporting_month": "June", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.465224+02	2026-01-11 15:36:51.46524+02	f	1	3	3	16
539	{"building": "Building 2401-1", "co2e_emissions": 17842.43, "consumption_tr": 118949.56, "reporting_year": 2020, "reporting_month": "June"}	2026-01-11 15:36:51.469442+02	2026-01-11 15:36:51.469462+02	f	1	3	3	17
540	{"building": "Building 2401-2", "co2e_emissions": 15984.17, "consumption_tr": 106561.14, "reporting_year": 2020, "reporting_month": "June"}	2026-01-11 15:36:51.473902+02	2026-01-11 15:36:51.473931+02	f	1	3	3	17
541	{"building": "Building 401", "co2e_emissions": 72354.15, "reporting_year": 2020, "consumption_kwh": 146170, "reporting_month": "July", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.478318+02	2026-01-11 15:36:51.478335+02	f	1	3	3	16
542	{"building": "Building 2401", "co2e_emissions": 75307.32, "reporting_year": 2020, "consumption_kwh": 152136, "reporting_month": "July", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.482913+02	2026-01-11 15:36:51.48293+02	f	1	3	3	16
543	{"building": "Building 2401-1", "co2e_emissions": 19980.3, "consumption_tr": 133202.02, "reporting_year": 2020, "reporting_month": "July"}	2026-01-11 15:36:51.488524+02	2026-01-11 15:36:51.488539+02	f	1	3	3	17
544	{"building": "Building 2401-2", "co2e_emissions": 19693.27, "consumption_tr": 131288.46, "reporting_year": 2020, "reporting_month": "July"}	2026-01-11 15:36:51.492133+02	2026-01-11 15:36:51.492147+02	f	1	3	3	17
545	{"building": "Building 401", "co2e_emissions": 56431.49, "reporting_year": 2020, "consumption_kwh": 114003, "reporting_month": "August", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.495542+02	2026-01-11 15:36:51.495583+02	f	1	3	3	16
546	{"building": "Building 2401", "co2e_emissions": 55972.12, "reporting_year": 2020, "consumption_kwh": 113075, "reporting_month": "August", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.498819+02	2026-01-11 15:36:51.498831+02	f	1	3	3	16
547	{"building": "Building 2401-1", "co2e_emissions": 23534.33, "consumption_tr": 156895.53, "reporting_year": 2020, "reporting_month": "August"}	2026-01-11 15:36:51.502112+02	2026-01-11 15:36:51.502127+02	f	1	3	3	17
548	{"building": "Building 2401-2", "co2e_emissions": 20403.64, "consumption_tr": 136024.24, "reporting_year": 2020, "reporting_month": "August"}	2026-01-11 15:36:51.505919+02	2026-01-11 15:36:51.505937+02	f	1	3	3	17
549	{"building": "Building 401", "co2e_emissions": 63730.75, "reporting_year": 2020, "consumption_kwh": 128749, "reporting_month": "September", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.510744+02	2026-01-11 15:36:51.510758+02	f	1	3	3	16
550	{"building": "Building 2401", "co2e_emissions": 59280.71, "reporting_year": 2020, "consumption_kwh": 119759, "reporting_month": "September", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.513946+02	2026-01-11 15:36:51.513957+02	f	1	3	3	16
551	{"building": "Building 2401-1", "co2e_emissions": 14928.72, "consumption_tr": 99524.8, "reporting_year": 2020, "reporting_month": "September"}	2026-01-11 15:36:51.517358+02	2026-01-11 15:36:51.517371+02	f	1	3	3	17
552	{"building": "Building 2401-2", "co2e_emissions": 17208.79, "consumption_tr": 114725.28, "reporting_year": 2020, "reporting_month": "September"}	2026-01-11 15:36:51.520737+02	2026-01-11 15:36:51.520754+02	f	1	3	3	17
553	{"building": "Building 401", "co2e_emissions": 63100.62, "reporting_year": 2020, "consumption_kwh": 127476, "reporting_month": "October", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.526212+02	2026-01-11 15:36:51.526227+02	f	1	3	3	16
554	{"building": "Building 2401", "co2e_emissions": 63663.93, "reporting_year": 2020, "consumption_kwh": 128614, "reporting_month": "October", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.529644+02	2026-01-11 15:36:51.529655+02	f	1	3	3	16
555	{"building": "Building 2401-1", "co2e_emissions": 19007.31, "consumption_tr": 126715.39, "reporting_year": 2020, "reporting_month": "October"}	2026-01-11 15:36:51.532974+02	2026-01-11 15:36:51.532985+02	f	1	3	3	17
556	{"building": "Building 2401-2", "co2e_emissions": 16441.21, "consumption_tr": 109608.04, "reporting_year": 2020, "reporting_month": "October"}	2026-01-11 15:36:51.536427+02	2026-01-11 15:36:51.536444+02	f	1	3	3	17
557	{"building": "Building 401", "co2e_emissions": 57404.16, "reporting_year": 2020, "consumption_kwh": 115968, "reporting_month": "November", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.540298+02	2026-01-11 15:36:51.540313+02	f	1	3	3	16
558	{"building": "Building 2401", "co2e_emissions": 58845.6, "reporting_year": 2020, "consumption_kwh": 118880, "reporting_month": "November", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.544962+02	2026-01-11 15:36:51.544976+02	f	1	3	3	16
559	{"building": "Building 2401-1", "co2e_emissions": 11730.38, "consumption_tr": 78202.55, "reporting_year": 2020, "reporting_month": "November"}	2026-01-11 15:36:51.54842+02	2026-01-11 15:36:51.548435+02	f	1	3	3	17
560	{"building": "Building 2401-2", "co2e_emissions": 10840.93, "consumption_tr": 72272.87, "reporting_year": 2020, "reporting_month": "November"}	2026-01-11 15:36:51.551826+02	2026-01-11 15:36:51.551842+02	f	1	3	3	17
561	{"building": "Building 401", "co2e_emissions": 68135.76, "reporting_year": 2020, "consumption_kwh": 137648, "reporting_month": "December", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.555711+02	2026-01-11 15:36:51.555727+02	f	1	3	3	16
562	{"building": "Building 2401", "co2e_emissions": 64572.75, "reporting_year": 2020, "consumption_kwh": 130450, "reporting_month": "December", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.55938+02	2026-01-11 15:36:51.559394+02	f	1	3	3	16
563	{"building": "Building 2401-1", "co2e_emissions": 5461.29, "consumption_tr": 36408.61, "reporting_year": 2020, "reporting_month": "December"}	2026-01-11 15:36:51.563194+02	2026-01-11 15:36:51.563206+02	f	1	3	3	17
564	{"building": "Building 2401-2", "co2e_emissions": 4908.3, "consumption_tr": 32722.01, "reporting_year": 2020, "reporting_month": "December"}	2026-01-11 15:36:51.567818+02	2026-01-11 15:36:51.567833+02	f	1	3	3	17
565	{"building": "Building 401", "co2e_emissions": 62330.89, "reporting_year": 2021, "consumption_kwh": 125921, "reporting_month": "January", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.571327+02	2026-01-11 15:36:51.571342+02	f	1	3	3	16
566	{"building": "Building 2401", "co2e_emissions": 61503.25, "reporting_year": 2021, "consumption_kwh": 124249, "reporting_month": "January", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.578089+02	2026-01-11 15:36:51.578104+02	f	1	3	3	16
567	{"building": "Building 2401-1", "co2e_emissions": 1774.97, "consumption_tr": 11833.17, "reporting_year": 2021, "reporting_month": "January"}	2026-01-11 15:36:51.584895+02	2026-01-11 15:36:51.58491+02	f	1	3	3	17
568	{"building": "Building 2401-2", "co2e_emissions": 1484.15, "consumption_tr": 9894.34, "reporting_year": 2021, "reporting_month": "January"}	2026-01-11 15:36:51.591699+02	2026-01-11 15:36:51.591712+02	f	1	3	3	17
569	{"building": "Building 401", "co2e_emissions": 54201.51, "reporting_year": 2021, "consumption_kwh": 109498, "reporting_month": "February", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.598601+02	2026-01-11 15:36:51.59862+02	f	1	3	3	16
570	{"building": "Building 2401", "co2e_emissions": 50692.95, "reporting_year": 2021, "consumption_kwh": 102410, "reporting_month": "February", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.602472+02	2026-01-11 15:36:51.602486+02	f	1	3	3	16
571	{"building": "Building 2401-1", "co2e_emissions": 1185.56, "consumption_tr": 7903.71, "reporting_year": 2021, "reporting_month": "February"}	2026-01-11 15:36:51.60633+02	2026-01-11 15:36:51.606343+02	f	1	3	3	17
572	{"building": "Building 2401-2", "co2e_emissions": 1109.59, "consumption_tr": 7397.28, "reporting_year": 2021, "reporting_month": "February"}	2026-01-11 15:36:51.609705+02	2026-01-11 15:36:51.609718+02	f	1	3	3	17
573	{"building": "Building 401", "co2e_emissions": 52503.17, "reporting_year": 2021, "consumption_kwh": 106067, "reporting_month": "March", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.61283+02	2026-01-11 15:36:51.612842+02	f	1	3	3	16
574	{"building": "Building 2401", "co2e_emissions": 49108.46, "reporting_year": 2021, "consumption_kwh": 99209, "reporting_month": "March", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.618255+02	2026-01-11 15:36:51.618271+02	f	1	3	3	16
575	{"building": "Building 2401-1", "co2e_emissions": 6466.41, "consumption_tr": 43109.4, "reporting_year": 2021, "reporting_month": "March"}	2026-01-11 15:36:51.623142+02	2026-01-11 15:36:51.623155+02	f	1	3	3	17
576	{"building": "Building 2401-2", "co2e_emissions": 6879.03, "consumption_tr": 45860.23, "reporting_year": 2021, "reporting_month": "March"}	2026-01-11 15:36:51.626562+02	2026-01-11 15:36:51.626576+02	f	1	3	3	17
577	{"building": "Building 401", "co2e_emissions": 59275.26, "reporting_year": 2021, "consumption_kwh": 119748, "reporting_month": "April", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.630501+02	2026-01-11 15:36:51.630517+02	f	1	3	3	16
578	{"building": "Building 2401", "co2e_emissions": 61519.59, "reporting_year": 2021, "consumption_kwh": 124282, "reporting_month": "April", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.634124+02	2026-01-11 15:36:51.634138+02	f	1	3	3	16
579	{"building": "Building 2401-1", "co2e_emissions": 6345.3, "consumption_tr": 42301.97, "reporting_year": 2021, "reporting_month": "April"}	2026-01-11 15:36:51.638776+02	2026-01-11 15:36:51.638789+02	f	1	3	3	17
580	{"building": "Building 2401-2", "co2e_emissions": 7052.81, "consumption_tr": 47018.72, "reporting_year": 2021, "reporting_month": "April"}	2026-01-11 15:36:51.642129+02	2026-01-11 15:36:51.642142+02	f	1	3	3	17
581	{"building": "Building 401", "co2e_emissions": 54885.6, "reporting_year": 2021, "consumption_kwh": 110880, "reporting_month": "May", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.646805+02	2026-01-11 15:36:51.646821+02	f	1	3	3	16
582	{"building": "Building 2401", "co2e_emissions": 57494.25, "reporting_year": 2021, "consumption_kwh": 116150, "reporting_month": "May", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.650116+02	2026-01-11 15:36:51.650128+02	f	1	3	3	16
583	{"building": "Building 2401-1", "co2e_emissions": 15804.93, "consumption_tr": 105366.23, "reporting_year": 2021, "reporting_month": "May"}	2026-01-11 15:36:51.653409+02	2026-01-11 15:36:51.653421+02	f	1	3	3	17
584	{"building": "Building 2401-2", "co2e_emissions": 14301.24, "consumption_tr": 95341.61, "reporting_year": 2021, "reporting_month": "May"}	2026-01-11 15:36:51.65777+02	2026-01-11 15:36:51.657783+02	f	1	3	3	17
585	{"building": "Building 401", "co2e_emissions": 53532.76, "reporting_year": 2021, "consumption_kwh": 108147, "reporting_month": "June", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.662636+02	2026-01-11 15:36:51.662651+02	f	1	3	3	16
586	{"building": "Building 2401", "co2e_emissions": 53358.53, "reporting_year": 2021, "consumption_kwh": 107795, "reporting_month": "June", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.667467+02	2026-01-11 15:36:51.667479+02	f	1	3	3	16
587	{"building": "Building 2401-1", "co2e_emissions": 18740.28, "consumption_tr": 124935.22, "reporting_year": 2021, "reporting_month": "June"}	2026-01-11 15:36:51.67064+02	2026-01-11 15:36:51.670651+02	f	1	3	3	17
588	{"building": "Building 2401-2", "co2e_emissions": 19097.23, "consumption_tr": 127314.88, "reporting_year": 2021, "reporting_month": "June"}	2026-01-11 15:36:51.674336+02	2026-01-11 15:36:51.674346+02	f	1	3	3	17
589	{"building": "Building 401", "co2e_emissions": 75433.05, "reporting_year": 2021, "consumption_kwh": 152390, "reporting_month": "July", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.678358+02	2026-01-11 15:36:51.678373+02	f	1	3	3	16
590	{"building": "Building 2401", "co2e_emissions": 76223.07, "reporting_year": 2021, "consumption_kwh": 153986, "reporting_month": "July", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.683469+02	2026-01-11 15:36:51.683481+02	f	1	3	3	16
591	{"building": "Building 2401-1", "co2e_emissions": 20735.67, "consumption_tr": 138237.79, "reporting_year": 2021, "reporting_month": "July"}	2026-01-11 15:36:51.688315+02	2026-01-11 15:36:51.688326+02	f	1	3	3	17
592	{"building": "Building 2401-2", "co2e_emissions": 18600.87, "consumption_tr": 124005.78, "reporting_year": 2021, "reporting_month": "July"}	2026-01-11 15:36:51.691685+02	2026-01-11 15:36:51.691701+02	f	1	3	3	17
593	{"building": "Building 401", "co2e_emissions": 59999.94, "reporting_year": 2021, "consumption_kwh": 121212, "reporting_month": "August", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.69544+02	2026-01-11 15:36:51.695454+02	f	1	3	3	16
594	{"building": "Building 2401", "co2e_emissions": 59118.35, "reporting_year": 2021, "consumption_kwh": 119431, "reporting_month": "August", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.701591+02	2026-01-11 15:36:51.701602+02	f	1	3	3	16
595	{"building": "Building 2401-1", "co2e_emissions": 19615.86, "consumption_tr": 130772.37, "reporting_year": 2021, "reporting_month": "August"}	2026-01-11 15:36:51.705548+02	2026-01-11 15:36:51.705573+02	f	1	3	3	17
596	{"building": "Building 2401-2", "co2e_emissions": 23634.04, "consumption_tr": 157560.29, "reporting_year": 2021, "reporting_month": "August"}	2026-01-11 15:36:51.709647+02	2026-01-11 15:36:51.709663+02	f	1	3	3	17
597	{"building": "Building 401", "co2e_emissions": 67323.96, "reporting_year": 2021, "consumption_kwh": 136008, "reporting_month": "September", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.713935+02	2026-01-11 15:36:51.713951+02	f	1	3	3	16
598	{"building": "Building 2401", "co2e_emissions": 62341.78, "reporting_year": 2021, "consumption_kwh": 125943, "reporting_month": "September", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.718054+02	2026-01-11 15:36:51.718071+02	f	1	3	3	16
599	{"building": "Building 2401-1", "co2e_emissions": 17399.63, "consumption_tr": 115997.52, "reporting_year": 2021, "reporting_month": "September"}	2026-01-11 15:36:51.722278+02	2026-01-11 15:36:51.7223+02	f	1	3	3	17
600	{"building": "Building 2401-2", "co2e_emissions": 21213.52, "consumption_tr": 141423.46, "reporting_year": 2021, "reporting_month": "September"}	2026-01-11 15:36:51.72958+02	2026-01-11 15:36:51.729609+02	f	1	3	3	17
601	{"building": "Building 401", "co2e_emissions": 65101.9, "reporting_year": 2021, "consumption_kwh": 131519, "reporting_month": "October", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.735458+02	2026-01-11 15:36:51.735475+02	f	1	3	3	16
602	{"building": "Building 2401", "co2e_emissions": 67114.57, "reporting_year": 2021, "consumption_kwh": 135585, "reporting_month": "October", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.739493+02	2026-01-11 15:36:51.739509+02	f	1	3	3	16
603	{"building": "Building 2401-1", "co2e_emissions": 15025.78, "consumption_tr": 100171.85, "reporting_year": 2021, "reporting_month": "October"}	2026-01-11 15:36:51.743404+02	2026-01-11 15:36:51.743418+02	f	1	3	3	17
604	{"building": "Building 2401-2", "co2e_emissions": 17199.15, "consumption_tr": 114661.03, "reporting_year": 2021, "reporting_month": "October"}	2026-01-11 15:36:51.746983+02	2026-01-11 15:36:51.746995+02	f	1	3	3	17
605	{"building": "Building 401", "co2e_emissions": 61747.78, "reporting_year": 2021, "consumption_kwh": 124743, "reporting_month": "November", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.751211+02	2026-01-11 15:36:51.751222+02	f	1	3	3	16
606	{"building": "Building 2401", "co2e_emissions": 57721.46, "reporting_year": 2021, "consumption_kwh": 116609, "reporting_month": "November", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.754879+02	2026-01-11 15:36:51.754894+02	f	1	3	3	16
607	{"building": "Building 2401-1", "co2e_emissions": 12901.29, "consumption_tr": 86008.59, "reporting_year": 2021, "reporting_month": "November"}	2026-01-11 15:36:51.760312+02	2026-01-11 15:36:51.760324+02	f	1	3	3	17
608	{"building": "Building 2401-2", "co2e_emissions": 11232.03, "consumption_tr": 74880.18, "reporting_year": 2021, "reporting_month": "November"}	2026-01-11 15:36:51.764118+02	2026-01-11 15:36:51.76413+02	f	1	3	3	17
609	{"building": "Building 401", "co2e_emissions": 65917.66, "reporting_year": 2021, "consumption_kwh": 133167, "reporting_month": "December", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.7679+02	2026-01-11 15:36:51.767939+02	f	1	3	3	16
610	{"building": "Building 2401", "co2e_emissions": 69469.29, "reporting_year": 2021, "consumption_kwh": 140342, "reporting_month": "December", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.771806+02	2026-01-11 15:36:51.771822+02	f	1	3	3	16
611	{"building": "Building 2401-1", "co2e_emissions": 6867.51, "consumption_tr": 45783.38, "reporting_year": 2021, "reporting_month": "December"}	2026-01-11 15:36:51.776391+02	2026-01-11 15:36:51.776406+02	f	1	3	3	17
612	{"building": "Building 2401-2", "co2e_emissions": 6146.49, "consumption_tr": 40976.6, "reporting_year": 2021, "reporting_month": "December"}	2026-01-11 15:36:51.780123+02	2026-01-11 15:36:51.780135+02	f	1	3	3	17
613	{"building": "Building 401", "co2e_emissions": 64478.7, "reporting_year": 2022, "consumption_kwh": 130260, "reporting_month": "January", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.784213+02	2026-01-11 15:36:51.78423+02	f	1	3	3	16
614	{"building": "Building 2401", "co2e_emissions": 61502.76, "reporting_year": 2022, "consumption_kwh": 124248, "reporting_month": "January", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.789583+02	2026-01-11 15:36:51.789599+02	f	1	3	3	16
615	{"building": "Building 2401-1", "co2e_emissions": 1852.06, "consumption_tr": 12347.05, "reporting_year": 2022, "reporting_month": "January"}	2026-01-11 15:36:51.795099+02	2026-01-11 15:36:51.795112+02	f	1	3	3	17
616	{"building": "Building 2401-2", "co2e_emissions": 1538.35, "consumption_tr": 10255.64, "reporting_year": 2022, "reporting_month": "January"}	2026-01-11 15:36:51.798912+02	2026-01-11 15:36:51.798923+02	f	1	3	3	17
617	{"building": "Building 401", "co2e_emissions": 56005.29, "reporting_year": 2022, "consumption_kwh": 113142, "reporting_month": "February", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.802503+02	2026-01-11 15:36:51.802519+02	f	1	3	3	16
618	{"building": "Building 2401", "co2e_emissions": 55014.79, "reporting_year": 2022, "consumption_kwh": 111141, "reporting_month": "February", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.806218+02	2026-01-11 15:36:51.806229+02	f	1	3	3	16
619	{"building": "Building 2401-1", "co2e_emissions": 1273.13, "consumption_tr": 8487.5, "reporting_year": 2022, "reporting_month": "February"}	2026-01-11 15:36:51.809911+02	2026-01-11 15:36:51.809922+02	f	1	3	3	17
620	{"building": "Building 2401-2", "co2e_emissions": 1334.92, "consumption_tr": 8899.46, "reporting_year": 2022, "reporting_month": "February"}	2026-01-11 15:36:51.815186+02	2026-01-11 15:36:51.8152+02	f	1	3	3	17
621	{"building": "Building 401", "co2e_emissions": 54048.56, "reporting_year": 2022, "consumption_kwh": 109189, "reporting_month": "March", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.819366+02	2026-01-11 15:36:51.819382+02	f	1	3	3	16
622	{"building": "Building 2401", "co2e_emissions": 53770.86, "reporting_year": 2022, "consumption_kwh": 108628, "reporting_month": "March", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.823353+02	2026-01-11 15:36:51.823368+02	f	1	3	3	16
623	{"building": "Building 2401-1", "co2e_emissions": 7171.54, "consumption_tr": 47810.24, "reporting_year": 2022, "reporting_month": "March"}	2026-01-11 15:36:51.827071+02	2026-01-11 15:36:51.827086+02	f	1	3	3	17
624	{"building": "Building 2401-2", "co2e_emissions": 7255.31, "consumption_tr": 48368.7, "reporting_year": 2022, "reporting_month": "March"}	2026-01-11 15:36:51.832278+02	2026-01-11 15:36:51.832295+02	f	1	3	3	17
625	{"building": "Building 401", "co2e_emissions": 57452.18, "reporting_year": 2022, "consumption_kwh": 116065, "reporting_month": "April", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.838204+02	2026-01-11 15:36:51.838224+02	f	1	3	3	16
626	{"building": "Building 2401", "co2e_emissions": 58495.14, "reporting_year": 2022, "consumption_kwh": 118172, "reporting_month": "April", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.842508+02	2026-01-11 15:36:51.842522+02	f	1	3	3	16
627	{"building": "Building 2401-1", "co2e_emissions": 7431.64, "consumption_tr": 49544.24, "reporting_year": 2022, "reporting_month": "April"}	2026-01-11 15:36:51.84632+02	2026-01-11 15:36:51.846336+02	f	1	3	3	17
628	{"building": "Building 2401-2", "co2e_emissions": 6711.4, "consumption_tr": 44742.66, "reporting_year": 2022, "reporting_month": "April"}	2026-01-11 15:36:51.850207+02	2026-01-11 15:36:51.850222+02	f	1	3	3	17
629	{"building": "Building 401", "co2e_emissions": 55539.99, "reporting_year": 2022, "consumption_kwh": 112202, "reporting_month": "May", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.854805+02	2026-01-11 15:36:51.854816+02	f	1	3	3	16
630	{"building": "Building 2401", "co2e_emissions": 54407.43, "reporting_year": 2022, "consumption_kwh": 109914, "reporting_month": "May", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.858506+02	2026-01-11 15:36:51.858517+02	f	1	3	3	16
631	{"building": "Building 2401-1", "co2e_emissions": 15544.21, "consumption_tr": 103628.07, "reporting_year": 2022, "reporting_month": "May"}	2026-01-11 15:36:51.862236+02	2026-01-11 15:36:51.862255+02	f	1	3	3	17
632	{"building": "Building 2401-2", "co2e_emissions": 13811.77, "consumption_tr": 92078.48, "reporting_year": 2022, "reporting_month": "May"}	2026-01-11 15:36:51.86622+02	2026-01-11 15:36:51.866236+02	f	1	3	3	17
633	{"building": "Building 401", "co2e_emissions": 58178.83, "reporting_year": 2022, "consumption_kwh": 117533, "reporting_month": "June", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.869994+02	2026-01-11 15:36:51.870008+02	f	1	3	3	16
634	{"building": "Building 2401", "co2e_emissions": 54277.74, "reporting_year": 2022, "consumption_kwh": 109652, "reporting_month": "June", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.87567+02	2026-01-11 15:36:51.875682+02	f	1	3	3	16
635	{"building": "Building 2401-1", "co2e_emissions": 17249.87, "consumption_tr": 114999.15, "reporting_year": 2022, "reporting_month": "June"}	2026-01-11 15:36:51.879936+02	2026-01-11 15:36:51.879952+02	f	1	3	3	17
636	{"building": "Building 2401-2", "co2e_emissions": 18664.58, "consumption_tr": 124430.51, "reporting_year": 2022, "reporting_month": "June"}	2026-01-11 15:36:51.883453+02	2026-01-11 15:36:51.883464+02	f	1	3	3	17
637	{"building": "Building 401", "co2e_emissions": 78252.57, "reporting_year": 2022, "consumption_kwh": 158086, "reporting_month": "July", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.887008+02	2026-01-11 15:36:51.887018+02	f	1	3	3	16
638	{"building": "Building 2401", "co2e_emissions": 77965.96, "reporting_year": 2022, "consumption_kwh": 157507, "reporting_month": "July", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.890369+02	2026-01-11 15:36:51.89038+02	f	1	3	3	16
639	{"building": "Building 2401-1", "co2e_emissions": 19707.13, "consumption_tr": 131380.89, "reporting_year": 2022, "reporting_month": "July"}	2026-01-11 15:36:51.895329+02	2026-01-11 15:36:51.895344+02	f	1	3	3	17
640	{"building": "Building 2401-2", "co2e_emissions": 23347.85, "consumption_tr": 155652.36, "reporting_year": 2022, "reporting_month": "July"}	2026-01-11 15:36:51.899814+02	2026-01-11 15:36:51.899828+02	f	1	3	3	17
641	{"building": "Building 401", "co2e_emissions": 63058.05, "reporting_year": 2022, "consumption_kwh": 127390, "reporting_month": "August", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.903327+02	2026-01-11 15:36:51.903342+02	f	1	3	3	16
642	{"building": "Building 2401", "co2e_emissions": 59310.9, "reporting_year": 2022, "consumption_kwh": 119820, "reporting_month": "August", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.906976+02	2026-01-11 15:36:51.906993+02	f	1	3	3	16
643	{"building": "Building 2401-1", "co2e_emissions": 22433.56, "consumption_tr": 149557.08, "reporting_year": 2022, "reporting_month": "August"}	2026-01-11 15:36:51.914024+02	2026-01-11 15:36:51.91404+02	f	1	3	3	17
644	{"building": "Building 2401-2", "co2e_emissions": 24281.25, "consumption_tr": 161875.02, "reporting_year": 2022, "reporting_month": "August"}	2026-01-11 15:36:51.918978+02	2026-01-11 15:36:51.918993+02	f	1	3	3	17
645	{"building": "Building 401", "co2e_emissions": 68737.68, "reporting_year": 2022, "consumption_kwh": 138864, "reporting_month": "September", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.923149+02	2026-01-11 15:36:51.923165+02	f	1	3	3	16
646	{"building": "Building 2401", "co2e_emissions": 63887.18, "reporting_year": 2022, "consumption_kwh": 129065, "reporting_month": "September", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.928761+02	2026-01-11 15:36:51.928789+02	f	1	3	3	16
647	{"building": "Building 2401-1", "co2e_emissions": 20314.61, "consumption_tr": 135430.71, "reporting_year": 2022, "reporting_month": "September"}	2026-01-11 15:36:51.934894+02	2026-01-11 15:36:51.93491+02	f	1	3	3	17
648	{"building": "Building 2401-2", "co2e_emissions": 18293.5, "consumption_tr": 121956.68, "reporting_year": 2022, "reporting_month": "September"}	2026-01-11 15:36:51.938877+02	2026-01-11 15:36:51.938892+02	f	1	3	3	17
649	{"building": "Building 401", "co2e_emissions": 70606.3, "reporting_year": 2022, "consumption_kwh": 142639, "reporting_month": "October", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.94292+02	2026-01-11 15:36:51.942936+02	f	1	3	3	16
650	{"building": "Building 2401", "co2e_emissions": 69765.3, "reporting_year": 2022, "consumption_kwh": 140940, "reporting_month": "October", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.946304+02	2026-01-11 15:36:51.946317+02	f	1	3	3	16
651	{"building": "Building 2401-1", "co2e_emissions": 16145.47, "consumption_tr": 107636.5, "reporting_year": 2022, "reporting_month": "October"}	2026-01-11 15:36:51.951754+02	2026-01-11 15:36:51.95177+02	f	1	3	3	17
652	{"building": "Building 2401-2", "co2e_emissions": 19476.98, "consumption_tr": 129846.52, "reporting_year": 2022, "reporting_month": "October"}	2026-01-11 15:36:51.955968+02	2026-01-11 15:36:51.95599+02	f	1	3	3	17
653	{"building": "Building 401", "co2e_emissions": 56621.57, "reporting_year": 2022, "consumption_kwh": 114387, "reporting_month": "November", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.960171+02	2026-01-11 15:36:51.960186+02	f	1	3	3	16
654	{"building": "Building 2401", "co2e_emissions": 60819.66, "reporting_year": 2022, "consumption_kwh": 122868, "reporting_month": "November", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.973879+02	2026-01-11 15:36:51.973897+02	f	1	3	3	16
655	{"building": "Building 2401-1", "co2e_emissions": 13150.9, "consumption_tr": 87672.68, "reporting_year": 2022, "reporting_month": "November"}	2026-01-11 15:36:51.981118+02	2026-01-11 15:36:51.981131+02	f	1	3	3	17
656	{"building": "Building 2401-2", "co2e_emissions": 11490.39, "consumption_tr": 76602.58, "reporting_year": 2022, "reporting_month": "November"}	2026-01-11 15:36:51.986463+02	2026-01-11 15:36:51.986481+02	f	1	3	3	17
657	{"building": "Building 401", "co2e_emissions": 69591.55, "reporting_year": 2022, "consumption_kwh": 140589, "reporting_month": "December", "grid_emission_factor": 0.495}	2026-01-11 15:36:51.994425+02	2026-01-11 15:36:51.994439+02	f	1	3	3	16
658	{"building": "Building 2401", "co2e_emissions": 69014.88, "reporting_year": 2022, "consumption_kwh": 139424, "reporting_month": "December", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.003418+02	2026-01-11 15:36:52.003434+02	f	1	3	3	16
659	{"building": "Building 2401-1", "co2e_emissions": 5376.51, "consumption_tr": 35843.39, "reporting_year": 2022, "reporting_month": "December"}	2026-01-11 15:36:52.008396+02	2026-01-11 15:36:52.008412+02	f	1	3	3	17
660	{"building": "Building 2401-2", "co2e_emissions": 6286.11, "consumption_tr": 41907.39, "reporting_year": 2022, "reporting_month": "December"}	2026-01-11 15:36:52.012178+02	2026-01-11 15:36:52.012191+02	f	1	3	3	17
661	{"building": "Building 401", "co2e_emissions": 57794.22, "reporting_year": 2023, "consumption_kwh": 116756, "reporting_month": "January", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.015686+02	2026-01-11 15:36:52.0157+02	f	1	3	3	16
662	{"building": "Building 2401", "co2e_emissions": 59021.82, "reporting_year": 2023, "consumption_kwh": 119236, "reporting_month": "January", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.019577+02	2026-01-11 15:36:52.019592+02	f	1	3	3	16
663	{"building": "Building 2401-1", "co2e_emissions": 1576.04, "consumption_tr": 10506.94, "reporting_year": 2023, "reporting_month": "January"}	2026-01-11 15:36:52.024942+02	2026-01-11 15:36:52.024957+02	f	1	3	3	17
664	{"building": "Building 2401-2", "co2e_emissions": 1462.64, "consumption_tr": 9750.95, "reporting_year": 2023, "reporting_month": "January"}	2026-01-11 15:36:52.028592+02	2026-01-11 15:36:52.028608+02	f	1	3	3	17
665	{"building": "Building 401", "co2e_emissions": 49109.44, "reporting_year": 2023, "consumption_kwh": 99211, "reporting_month": "February", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.032069+02	2026-01-11 15:36:52.032082+02	f	1	3	3	16
666	{"building": "Building 2401", "co2e_emissions": 52208.64, "reporting_year": 2023, "consumption_kwh": 105472, "reporting_month": "February", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.036257+02	2026-01-11 15:36:52.036273+02	f	1	3	3	16
667	{"building": "Building 2401-1", "co2e_emissions": 1092.61, "consumption_tr": 7284.09, "reporting_year": 2023, "reporting_month": "February"}	2026-01-11 15:36:52.039801+02	2026-01-11 15:36:52.039814+02	f	1	3	3	17
668	{"building": "Building 2401-2", "co2e_emissions": 1254.43, "consumption_tr": 8362.85, "reporting_year": 2023, "reporting_month": "February"}	2026-01-11 15:36:52.044669+02	2026-01-11 15:36:52.044681+02	f	1	3	3	17
669	{"building": "Building 401", "co2e_emissions": 48341.7, "reporting_year": 2023, "consumption_kwh": 97660, "reporting_month": "March", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.050376+02	2026-01-11 15:36:52.050408+02	f	1	3	3	16
670	{"building": "Building 2401", "co2e_emissions": 50233.1, "reporting_year": 2023, "consumption_kwh": 101481, "reporting_month": "March", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.054255+02	2026-01-11 15:36:52.054273+02	f	1	3	3	16
671	{"building": "Building 2401-1", "co2e_emissions": 6152.24, "consumption_tr": 41014.94, "reporting_year": 2023, "reporting_month": "March"}	2026-01-11 15:36:52.05812+02	2026-01-11 15:36:52.058135+02	f	1	3	3	17
672	{"building": "Building 2401-2", "co2e_emissions": 7511.85, "consumption_tr": 50079.0, "reporting_year": 2023, "reporting_month": "March"}	2026-01-11 15:36:52.061528+02	2026-01-11 15:36:52.061539+02	f	1	3	3	17
673	{"building": "Building 401", "co2e_emissions": 56802.74, "reporting_year": 2023, "consumption_kwh": 114753, "reporting_month": "April", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.067804+02	2026-01-11 15:36:52.06782+02	f	1	3	3	16
674	{"building": "Building 2401", "co2e_emissions": 55176.17, "reporting_year": 2023, "consumption_kwh": 111467, "reporting_month": "April", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.072978+02	2026-01-11 15:36:52.072994+02	f	1	3	3	16
675	{"building": "Building 2401-1", "co2e_emissions": 5868.06, "consumption_tr": 39120.42, "reporting_year": 2023, "reporting_month": "April"}	2026-01-11 15:36:52.076546+02	2026-01-11 15:36:52.076558+02	f	1	3	3	17
676	{"building": "Building 2401-2", "co2e_emissions": 6542.92, "consumption_tr": 43619.46, "reporting_year": 2023, "reporting_month": "April"}	2026-01-11 15:36:52.08025+02	2026-01-11 15:36:52.08027+02	f	1	3	3	17
677	{"building": "Building 401", "co2e_emissions": 51979.46, "reporting_year": 2023, "consumption_kwh": 105009, "reporting_month": "May", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.084815+02	2026-01-11 15:36:52.084834+02	f	1	3	3	16
678	{"building": "Building 2401", "co2e_emissions": 52081.43, "reporting_year": 2023, "consumption_kwh": 105215, "reporting_month": "May", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.09633+02	2026-01-11 15:36:52.096347+02	f	1	3	3	16
679	{"building": "Building 2401-1", "co2e_emissions": 16103.26, "consumption_tr": 107355.04, "reporting_year": 2023, "reporting_month": "May"}	2026-01-11 15:36:52.099985+02	2026-01-11 15:36:52.099999+02	f	1	3	3	17
680	{"building": "Building 2401-2", "co2e_emissions": 13219.96, "consumption_tr": 88133.09, "reporting_year": 2023, "reporting_month": "May"}	2026-01-11 15:36:52.103233+02	2026-01-11 15:36:52.103244+02	f	1	3	3	17
681	{"building": "Building 401", "co2e_emissions": 53671.36, "reporting_year": 2023, "consumption_kwh": 108427, "reporting_month": "June", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.106477+02	2026-01-11 15:36:52.10649+02	f	1	3	3	16
682	{"building": "Building 2401", "co2e_emissions": 52410.6, "reporting_year": 2023, "consumption_kwh": 105880, "reporting_month": "June", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.110381+02	2026-01-11 15:36:52.1104+02	f	1	3	3	16
683	{"building": "Building 2401-1", "co2e_emissions": 16617.68, "consumption_tr": 110784.51, "reporting_year": 2023, "reporting_month": "June"}	2026-01-11 15:36:52.114587+02	2026-01-11 15:36:52.114603+02	f	1	3	3	17
684	{"building": "Building 2401-2", "co2e_emissions": 19559.2, "consumption_tr": 130394.64, "reporting_year": 2023, "reporting_month": "June"}	2026-01-11 15:36:52.118559+02	2026-01-11 15:36:52.118574+02	f	1	3	3	17
685	{"building": "Building 401", "co2e_emissions": 68451.07, "reporting_year": 2023, "consumption_kwh": 138285, "reporting_month": "July", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.122369+02	2026-01-11 15:36:52.122382+02	f	1	3	3	16
686	{"building": "Building 2401", "co2e_emissions": 72316.53, "reporting_year": 2023, "consumption_kwh": 146094, "reporting_month": "July", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.126234+02	2026-01-11 15:36:52.126251+02	f	1	3	3	16
687	{"building": "Building 2401-1", "co2e_emissions": 21583.59, "consumption_tr": 143890.61, "reporting_year": 2023, "reporting_month": "July"}	2026-01-11 15:36:52.130109+02	2026-01-11 15:36:52.130125+02	f	1	3	3	17
688	{"building": "Building 2401-2", "co2e_emissions": 18231.03, "consumption_tr": 121540.17, "reporting_year": 2023, "reporting_month": "July"}	2026-01-11 15:36:52.134619+02	2026-01-11 15:36:52.134635+02	f	1	3	3	17
689	{"building": "Building 401", "co2e_emissions": 57875.4, "reporting_year": 2023, "consumption_kwh": 116920, "reporting_month": "August", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.144165+02	2026-01-11 15:36:52.144179+02	f	1	3	3	16
690	{"building": "Building 2401", "co2e_emissions": 57469.0, "reporting_year": 2023, "consumption_kwh": 116099, "reporting_month": "August", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.148129+02	2026-01-11 15:36:52.148141+02	f	1	3	3	16
691	{"building": "Building 2401-1", "co2e_emissions": 22669.07, "consumption_tr": 151127.15, "reporting_year": 2023, "reporting_month": "August"}	2026-01-11 15:36:52.152268+02	2026-01-11 15:36:52.152278+02	f	1	3	3	17
692	{"building": "Building 2401-2", "co2e_emissions": 21661.47, "consumption_tr": 144409.81, "reporting_year": 2023, "reporting_month": "August"}	2026-01-11 15:36:52.156152+02	2026-01-11 15:36:52.156162+02	f	1	3	3	17
693	{"building": "Building 401", "co2e_emissions": 60460.78, "reporting_year": 2023, "consumption_kwh": 122143, "reporting_month": "September", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.160519+02	2026-01-11 15:36:52.160532+02	f	1	3	3	16
694	{"building": "Building 2401", "co2e_emissions": 62332.88, "reporting_year": 2023, "consumption_kwh": 125925, "reporting_month": "September", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.163908+02	2026-01-11 15:36:52.163919+02	f	1	3	3	16
695	{"building": "Building 2401-1", "co2e_emissions": 18369.38, "consumption_tr": 122462.53, "reporting_year": 2023, "reporting_month": "September"}	2026-01-11 15:36:52.16722+02	2026-01-11 15:36:52.167235+02	f	1	3	3	17
696	{"building": "Building 2401-2", "co2e_emissions": 15474.2, "consumption_tr": 103161.36, "reporting_year": 2023, "reporting_month": "September"}	2026-01-11 15:36:52.171873+02	2026-01-11 15:36:52.171883+02	f	1	3	3	17
697	{"building": "Building 401", "co2e_emissions": 63394.65, "reporting_year": 2023, "consumption_kwh": 128070, "reporting_month": "October", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.176008+02	2026-01-11 15:36:52.176033+02	f	1	3	3	16
698	{"building": "Building 2401", "co2e_emissions": 67305.65, "reporting_year": 2023, "consumption_kwh": 135971, "reporting_month": "October", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.179495+02	2026-01-11 15:36:52.179505+02	f	1	3	3	16
699	{"building": "Building 2401-1", "co2e_emissions": 16732.3, "consumption_tr": 111548.68, "reporting_year": 2023, "reporting_month": "October"}	2026-01-11 15:36:52.182847+02	2026-01-11 15:36:52.182858+02	f	1	3	3	17
700	{"building": "Building 2401-2", "co2e_emissions": 16597.67, "consumption_tr": 110651.12, "reporting_year": 2023, "reporting_month": "October"}	2026-01-11 15:36:52.187219+02	2026-01-11 15:36:52.187229+02	f	1	3	3	17
701	{"building": "Building 401", "co2e_emissions": 57362.08, "reporting_year": 2023, "consumption_kwh": 115883, "reporting_month": "November", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.191238+02	2026-01-11 15:36:52.191253+02	f	1	3	3	16
702	{"building": "Building 2401", "co2e_emissions": 58383.76, "reporting_year": 2023, "consumption_kwh": 117947, "reporting_month": "November", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.196731+02	2026-01-11 15:36:52.196744+02	f	1	3	3	16
703	{"building": "Building 2401-1", "co2e_emissions": 12447.31, "consumption_tr": 82982.04, "reporting_year": 2023, "reporting_month": "November"}	2026-01-11 15:36:52.200425+02	2026-01-11 15:36:52.200438+02	f	1	3	3	17
704	{"building": "Building 2401-2", "co2e_emissions": 10450.34, "consumption_tr": 69668.94, "reporting_year": 2023, "reporting_month": "November"}	2026-01-11 15:36:52.204072+02	2026-01-11 15:36:52.204089+02	f	1	3	3	17
705	{"building": "Building 401", "co2e_emissions": 61293.38, "reporting_year": 2023, "consumption_kwh": 123825, "reporting_month": "December", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.207955+02	2026-01-11 15:36:52.207971+02	f	1	3	3	16
706	{"building": "Building 2401", "co2e_emissions": 66002.31, "reporting_year": 2023, "consumption_kwh": 133338, "reporting_month": "December", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.212968+02	2026-01-11 15:36:52.212983+02	f	1	3	3	16
707	{"building": "Building 2401-1", "co2e_emissions": 5371.66, "consumption_tr": 35811.05, "reporting_year": 2023, "reporting_month": "December"}	2026-01-11 15:36:52.216742+02	2026-01-11 15:36:52.216755+02	f	1	3	3	17
708	{"building": "Building 2401-2", "co2e_emissions": 6028.39, "consumption_tr": 40189.29, "reporting_year": 2023, "reporting_month": "December"}	2026-01-11 15:36:52.22044+02	2026-01-11 15:36:52.220456+02	f	1	3	3	17
709	{"building": "Building 401", "co2e_emissions": 55581.07, "reporting_year": 2024, "consumption_kwh": 112285, "reporting_month": "January", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.22415+02	2026-01-11 15:36:52.224165+02	f	1	3	3	16
710	{"building": "Building 2401", "co2e_emissions": 59599.98, "reporting_year": 2024, "consumption_kwh": 120404, "reporting_month": "January", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.227702+02	2026-01-11 15:36:52.227718+02	f	1	3	3	16
711	{"building": "Building 2401-1", "co2e_emissions": 4449.65, "consumption_tr": 29664.32, "reporting_year": 2024, "reporting_month": "January"}	2026-01-11 15:36:52.232958+02	2026-01-11 15:36:52.232975+02	f	1	3	3	17
712	{"building": "Building 2401-2", "co2e_emissions": 4308.6, "consumption_tr": 28723.97, "reporting_year": 2024, "reporting_month": "January"}	2026-01-11 15:36:52.236651+02	2026-01-11 15:36:52.236667+02	f	1	3	3	17
713	{"building": "Building 401", "co2e_emissions": 47710.57, "reporting_year": 2024, "consumption_kwh": 96385, "reporting_month": "February", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.242044+02	2026-01-11 15:36:52.242059+02	f	1	3	3	16
714	{"building": "Building 2401", "co2e_emissions": 50974.6, "reporting_year": 2024, "consumption_kwh": 102979, "reporting_month": "February", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.245672+02	2026-01-11 15:36:52.245704+02	f	1	3	3	16
715	{"building": "Building 2401-1", "co2e_emissions": 4036.77, "consumption_tr": 26911.82, "reporting_year": 2024, "reporting_month": "February"}	2026-01-11 15:36:52.249138+02	2026-01-11 15:36:52.249152+02	f	1	3	3	17
716	{"building": "Building 2401-2", "co2e_emissions": 4468.89, "consumption_tr": 29792.57, "reporting_year": 2024, "reporting_month": "February"}	2026-01-11 15:36:52.253969+02	2026-01-11 15:36:52.253984+02	f	1	3	3	17
717	{"building": "Building 401", "co2e_emissions": 47654.14, "reporting_year": 2024, "consumption_kwh": 96271, "reporting_month": "March", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.257437+02	2026-01-11 15:36:52.257451+02	f	1	3	3	16
718	{"building": "Building 2401", "co2e_emissions": 48579.79, "reporting_year": 2024, "consumption_kwh": 98141, "reporting_month": "March", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.260711+02	2026-01-11 15:36:52.260724+02	f	1	3	3	16
719	{"building": "Building 2401-1", "co2e_emissions": 4667.78, "consumption_tr": 31118.56, "reporting_year": 2024, "reporting_month": "March"}	2026-01-11 15:36:52.263883+02	2026-01-11 15:36:52.263897+02	f	1	3	3	17
720	{"building": "Building 2401-2", "co2e_emissions": 5679.62, "consumption_tr": 37864.14, "reporting_year": 2024, "reporting_month": "March"}	2026-01-11 15:36:52.267556+02	2026-01-11 15:36:52.267573+02	f	1	3	3	17
721	{"building": "Building 401", "co2e_emissions": 46290.42, "reporting_year": 2024, "consumption_kwh": 93516, "reporting_month": "April", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.272519+02	2026-01-11 15:36:52.272534+02	f	1	3	3	16
722	{"building": "Building 2401", "co2e_emissions": 44476.74, "reporting_year": 2024, "consumption_kwh": 89852, "reporting_month": "April", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.275984+02	2026-01-11 15:36:52.275997+02	f	1	3	3	16
723	{"building": "Building 2401-1", "co2e_emissions": 9497.24, "consumption_tr": 63314.96, "reporting_year": 2024, "reporting_month": "April"}	2026-01-11 15:36:52.279758+02	2026-01-11 15:36:52.279772+02	f	1	3	3	17
724	{"building": "Building 2401-2", "co2e_emissions": 8004.7, "consumption_tr": 53364.65, "reporting_year": 2024, "reporting_month": "April"}	2026-01-11 15:36:52.283336+02	2026-01-11 15:36:52.283351+02	f	1	3	3	17
725	{"building": "Building 401", "co2e_emissions": 40360.82, "reporting_year": 2024, "consumption_kwh": 81537, "reporting_month": "May", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.286802+02	2026-01-11 15:36:52.286813+02	f	1	3	3	16
726	{"building": "Building 2401", "co2e_emissions": 39015.4, "reporting_year": 2024, "consumption_kwh": 78819, "reporting_month": "May", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.290767+02	2026-01-11 15:36:52.290778+02	f	1	3	3	16
727	{"building": "Building 2401-1", "co2e_emissions": 15436.83, "consumption_tr": 102912.18, "reporting_year": 2024, "reporting_month": "May"}	2026-01-11 15:36:52.294065+02	2026-01-11 15:36:52.294079+02	f	1	3	3	17
728	{"building": "Building 2401-2", "co2e_emissions": 12902.84, "consumption_tr": 86018.95, "reporting_year": 2024, "reporting_month": "May"}	2026-01-11 15:36:52.298197+02	2026-01-11 15:36:52.298214+02	f	1	3	3	17
729	{"building": "Building 401", "co2e_emissions": 50932.53, "reporting_year": 2024, "consumption_kwh": 102894, "reporting_month": "June", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.30221+02	2026-01-11 15:36:52.302225+02	f	1	3	3	16
730	{"building": "Building 2401", "co2e_emissions": 54748.98, "reporting_year": 2024, "consumption_kwh": 110604, "reporting_month": "June", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.305633+02	2026-01-11 15:36:52.305646+02	f	1	3	3	16
731	{"building": "Building 2401-1", "co2e_emissions": 18314.16, "consumption_tr": 122094.43, "reporting_year": 2024, "reporting_month": "June"}	2026-01-11 15:36:52.30891+02	2026-01-11 15:36:52.308922+02	f	1	3	3	17
732	{"building": "Building 2401-2", "co2e_emissions": 16930.49, "consumption_tr": 112869.9, "reporting_year": 2024, "reporting_month": "June"}	2026-01-11 15:36:52.312429+02	2026-01-11 15:36:52.312446+02	f	1	3	3	17
733	{"building": "Building 401", "co2e_emissions": 74184.66, "reporting_year": 2024, "consumption_kwh": 149868, "reporting_month": "July", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.318152+02	2026-01-11 15:36:52.318167+02	f	1	3	3	16
734	{"building": "Building 2401", "co2e_emissions": 77476.9, "reporting_year": 2024, "consumption_kwh": 156519, "reporting_month": "July", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.321942+02	2026-01-11 15:36:52.321955+02	f	1	3	3	16
735	{"building": "Building 2401-1", "co2e_emissions": 21653.93, "consumption_tr": 144359.53, "reporting_year": 2024, "reporting_month": "July"}	2026-01-11 15:36:52.325646+02	2026-01-11 15:36:52.325659+02	f	1	3	3	17
736	{"building": "Building 2401-2", "co2e_emissions": 25335.91, "consumption_tr": 168906.07, "reporting_year": 2024, "reporting_month": "July"}	2026-01-11 15:36:52.329784+02	2026-01-11 15:36:52.3298+02	f	1	3	3	17
737	{"building": "Building 401", "co2e_emissions": 68618.88, "reporting_year": 2024, "consumption_kwh": 138624, "reporting_month": "August", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.334389+02	2026-01-11 15:36:52.334402+02	f	1	3	3	16
738	{"building": "Building 2401", "co2e_emissions": 66326.04, "reporting_year": 2024, "consumption_kwh": 133992, "reporting_month": "August", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.33755+02	2026-01-11 15:36:52.337562+02	f	1	3	3	16
739	{"building": "Building 2401-1", "co2e_emissions": 25890.45, "consumption_tr": 172603.01, "reporting_year": 2024, "reporting_month": "August"}	2026-01-11 15:36:52.342153+02	2026-01-11 15:36:52.342165+02	f	1	3	3	17
740	{"building": "Building 2401-2", "co2e_emissions": 28478.31, "consumption_tr": 189855.37, "reporting_year": 2024, "reporting_month": "August"}	2026-01-11 15:36:52.346427+02	2026-01-11 15:36:52.346443+02	f	1	3	3	17
741	{"building": "Building 401", "co2e_emissions": 67935.78, "reporting_year": 2024, "consumption_kwh": 137244, "reporting_month": "September", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.34983+02	2026-01-11 15:36:52.349843+02	f	1	3	3	16
742	{"building": "Building 2401", "co2e_emissions": 69565.32, "reporting_year": 2024, "consumption_kwh": 140536, "reporting_month": "September", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.353145+02	2026-01-11 15:36:52.353156+02	f	1	3	3	16
743	{"building": "Building 2401-1", "co2e_emissions": 17586.15, "consumption_tr": 117240.98, "reporting_year": 2024, "reporting_month": "September"}	2026-01-11 15:36:52.356618+02	2026-01-11 15:36:52.356629+02	f	1	3	3	17
744	{"building": "Building 2401-2", "co2e_emissions": 18718.66, "consumption_tr": 124791.09, "reporting_year": 2024, "reporting_month": "September"}	2026-01-11 15:36:52.360287+02	2026-01-11 15:36:52.360304+02	f	1	3	3	17
745	{"building": "Building 401", "co2e_emissions": 69357.91, "reporting_year": 2024, "consumption_kwh": 140117, "reporting_month": "October", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.36389+02	2026-01-11 15:36:52.363903+02	f	1	3	3	16
746	{"building": "Building 2401", "co2e_emissions": 73198.62, "reporting_year": 2024, "consumption_kwh": 147876, "reporting_month": "October", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.370215+02	2026-01-11 15:36:52.370227+02	f	1	3	3	16
747	{"building": "Building 2401-1", "co2e_emissions": 21987.65, "consumption_tr": 146584.3, "reporting_year": 2024, "reporting_month": "October"}	2026-01-11 15:36:52.373496+02	2026-01-11 15:36:52.373509+02	f	1	3	3	17
748	{"building": "Building 2401-2", "co2e_emissions": 18158.49, "consumption_tr": 121056.62, "reporting_year": 2024, "reporting_month": "October"}	2026-01-11 15:36:52.378708+02	2026-01-11 15:36:52.378723+02	f	1	3	3	17
749	{"building": "Building 401", "co2e_emissions": 66122.1, "reporting_year": 2024, "consumption_kwh": 133580, "reporting_month": "November", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.383512+02	2026-01-11 15:36:52.383524+02	f	1	3	3	16
750	{"building": "Building 2401", "co2e_emissions": 70131.1, "reporting_year": 2024, "consumption_kwh": 141679, "reporting_month": "November", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.387103+02	2026-01-11 15:36:52.387115+02	f	1	3	3	16
751	{"building": "Building 2401-1", "co2e_emissions": 11790.96, "consumption_tr": 78606.39, "reporting_year": 2024, "reporting_month": "November"}	2026-01-11 15:36:52.390963+02	2026-01-11 15:36:52.39098+02	f	1	3	3	17
752	{"building": "Building 2401-2", "co2e_emissions": 12777.44, "consumption_tr": 85182.95, "reporting_year": 2024, "reporting_month": "November"}	2026-01-11 15:36:52.394926+02	2026-01-11 15:36:52.394942+02	f	1	3	3	17
753	{"building": "Building 401", "co2e_emissions": 69876.18, "reporting_year": 2024, "consumption_kwh": 141164, "reporting_month": "December", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.398491+02	2026-01-11 15:36:52.398506+02	f	1	3	3	16
754	{"building": "Building 2401", "co2e_emissions": 69447.51, "reporting_year": 2024, "consumption_kwh": 140298, "reporting_month": "December", "grid_emission_factor": 0.495}	2026-01-11 15:36:52.405082+02	2026-01-11 15:36:52.405101+02	f	1	3	3	16
755	{"building": "Building 2401-1", "co2e_emissions": 5948.79, "consumption_tr": 39658.63, "reporting_year": 2024, "reporting_month": "December"}	2026-01-11 15:36:52.409316+02	2026-01-11 15:36:52.409333+02	f	1	3	3	17
756	{"building": "Building 2401-2", "co2e_emissions": 6934.96, "consumption_tr": 46233.07, "reporting_year": 2024, "reporting_month": "December"}	2026-01-11 15:36:52.412707+02	2026-01-11 15:36:52.412722+02	f	1	3	3	17
757	{"source": "Municipal Supply", "wastewater_m3": 1174.0, "co2e_emissions": 475.06, "consumption_m3": 1381, "reporting_year": 2020, "reporting_month": "January"}	2026-01-11 15:36:52.461379+02	2026-01-11 15:36:52.461394+02	f	1	3	3	18
758	{"source": "Municipal Supply", "wastewater_m3": 1076.0, "co2e_emissions": 435.5, "consumption_m3": 1266, "reporting_year": 2020, "reporting_month": "February"}	2026-01-11 15:36:52.46505+02	2026-01-11 15:36:52.465065+02	f	1	3	3	18
759	{"source": "Municipal Supply", "wastewater_m3": 1140.0, "co2e_emissions": 461.3, "consumption_m3": 1341, "reporting_year": 2020, "reporting_month": "March"}	2026-01-11 15:36:52.468678+02	2026-01-11 15:36:52.468693+02	f	1	3	3	18
760	{"source": "Municipal Supply", "wastewater_m3": 1035.0, "co2e_emissions": 418.99, "consumption_m3": 1218, "reporting_year": 2020, "reporting_month": "April"}	2026-01-11 15:36:52.472062+02	2026-01-11 15:36:52.472076+02	f	1	3	3	18
761	{"source": "Municipal Supply", "wastewater_m3": 641.0, "co2e_emissions": 259.38, "consumption_m3": 754, "reporting_year": 2020, "reporting_month": "May"}	2026-01-11 15:36:52.475349+02	2026-01-11 15:36:52.475364+02	f	1	3	3	18
762	{"source": "Municipal Supply", "wastewater_m3": 637.0, "co2e_emissions": 257.66, "consumption_m3": 749, "reporting_year": 2020, "reporting_month": "June"}	2026-01-11 15:36:52.480156+02	2026-01-11 15:36:52.480172+02	f	1	3	3	18
763	{"source": "Municipal Supply", "wastewater_m3": 887.0, "co2e_emissions": 358.79, "consumption_m3": 1043, "reporting_year": 2020, "reporting_month": "July"}	2026-01-11 15:36:52.484348+02	2026-01-11 15:36:52.484365+02	f	1	3	3	18
764	{"source": "Municipal Supply", "wastewater_m3": 782.0, "co2e_emissions": 316.48, "consumption_m3": 920, "reporting_year": 2020, "reporting_month": "August"}	2026-01-11 15:36:52.487974+02	2026-01-11 15:36:52.487989+02	f	1	3	3	18
765	{"source": "Municipal Supply", "wastewater_m3": 871.0, "co2e_emissions": 352.6, "consumption_m3": 1025, "reporting_year": 2020, "reporting_month": "September"}	2026-01-11 15:36:52.491493+02	2026-01-11 15:36:52.491507+02	f	1	3	3	18
766	{"source": "Municipal Supply", "wastewater_m3": 854.0, "co2e_emissions": 345.72, "consumption_m3": 1005, "reporting_year": 2020, "reporting_month": "October"}	2026-01-11 15:36:52.495038+02	2026-01-11 15:36:52.495051+02	f	1	3	3	18
767	{"source": "Municipal Supply", "wastewater_m3": 1207.0, "co2e_emissions": 488.48, "consumption_m3": 1420, "reporting_year": 2020, "reporting_month": "November"}	2026-01-11 15:36:52.502046+02	2026-01-11 15:36:52.502062+02	f	1	3	3	18
768	{"source": "Municipal Supply", "wastewater_m3": 1090.0, "co2e_emissions": 441.01, "consumption_m3": 1282, "reporting_year": 2020, "reporting_month": "December"}	2026-01-11 15:36:52.505695+02	2026-01-11 15:36:52.505708+02	f	1	3	3	18
769	{"source": "Municipal Supply", "wastewater_m3": 1239.0, "co2e_emissions": 501.55, "consumption_m3": 1458, "reporting_year": 2021, "reporting_month": "January"}	2026-01-11 15:36:52.509212+02	2026-01-11 15:36:52.509224+02	f	1	3	3	18
770	{"source": "Municipal Supply", "wastewater_m3": 1278.0, "co2e_emissions": 517.03, "consumption_m3": 1503, "reporting_year": 2021, "reporting_month": "February"}	2026-01-11 15:36:52.512605+02	2026-01-11 15:36:52.51262+02	f	1	3	3	18
771	{"source": "Municipal Supply", "wastewater_m3": 1102.0, "co2e_emissions": 446.17, "consumption_m3": 1297, "reporting_year": 2021, "reporting_month": "March"}	2026-01-11 15:36:52.516874+02	2026-01-11 15:36:52.516893+02	f	1	3	3	18
772	{"source": "Municipal Supply", "wastewater_m3": 1068.0, "co2e_emissions": 432.41, "consumption_m3": 1257, "reporting_year": 2021, "reporting_month": "April"}	2026-01-11 15:36:52.523239+02	2026-01-11 15:36:52.523254+02	f	1	3	3	18
773	{"source": "Municipal Supply", "wastewater_m3": 609.0, "co2e_emissions": 246.3, "consumption_m3": 716, "reporting_year": 2021, "reporting_month": "May"}	2026-01-11 15:36:52.528514+02	2026-01-11 15:36:52.528528+02	f	1	3	3	18
774	{"source": "Municipal Supply", "wastewater_m3": 655.0, "co2e_emissions": 265.22, "consumption_m3": 771, "reporting_year": 2021, "reporting_month": "June"}	2026-01-11 15:36:52.53254+02	2026-01-11 15:36:52.532556+02	f	1	3	3	18
775	{"source": "Municipal Supply", "wastewater_m3": 839.0, "co2e_emissions": 339.53, "consumption_m3": 987, "reporting_year": 2021, "reporting_month": "July"}	2026-01-11 15:36:52.535896+02	2026-01-11 15:36:52.53591+02	f	1	3	3	18
776	{"source": "Municipal Supply", "wastewater_m3": 881.0, "co2e_emissions": 356.38, "consumption_m3": 1036, "reporting_year": 2021, "reporting_month": "August"}	2026-01-11 15:36:52.539079+02	2026-01-11 15:36:52.539099+02	f	1	3	3	18
777	{"source": "Municipal Supply", "wastewater_m3": 818.0, "co2e_emissions": 330.93, "consumption_m3": 962, "reporting_year": 2021, "reporting_month": "September"}	2026-01-11 15:36:52.542702+02	2026-01-11 15:36:52.542715+02	f	1	3	3	18
778	{"source": "Municipal Supply", "wastewater_m3": 924.0, "co2e_emissions": 373.93, "consumption_m3": 1087, "reporting_year": 2021, "reporting_month": "October"}	2026-01-11 15:36:52.546422+02	2026-01-11 15:36:52.546443+02	f	1	3	3	18
779	{"source": "Municipal Supply", "wastewater_m3": 1198.0, "co2e_emissions": 485.04, "consumption_m3": 1410, "reporting_year": 2021, "reporting_month": "November"}	2026-01-11 15:36:52.549952+02	2026-01-11 15:36:52.549967+02	f	1	3	3	18
780	{"source": "Municipal Supply", "wastewater_m3": 1146.0, "co2e_emissions": 463.71, "consumption_m3": 1348, "reporting_year": 2021, "reporting_month": "December"}	2026-01-11 15:36:52.553346+02	2026-01-11 15:36:52.553359+02	f	1	3	3	18
781	{"source": "Municipal Supply", "wastewater_m3": 1243.0, "co2e_emissions": 502.93, "consumption_m3": 1462, "reporting_year": 2022, "reporting_month": "January"}	2026-01-11 15:36:52.560406+02	2026-01-11 15:36:52.560424+02	f	1	3	3	18
782	{"source": "Municipal Supply", "wastewater_m3": 1292.0, "co2e_emissions": 522.88, "consumption_m3": 1520, "reporting_year": 2022, "reporting_month": "February"}	2026-01-11 15:36:52.564193+02	2026-01-11 15:36:52.564218+02	f	1	3	3	18
783	{"source": "Municipal Supply", "wastewater_m3": 1028.0, "co2e_emissions": 415.9, "consumption_m3": 1209, "reporting_year": 2022, "reporting_month": "March"}	2026-01-11 15:36:52.568076+02	2026-01-11 15:36:52.56809+02	f	1	3	3	18
784	{"source": "Municipal Supply", "wastewater_m3": 1120.0, "co2e_emissions": 453.39, "consumption_m3": 1318, "reporting_year": 2022, "reporting_month": "April"}	2026-01-11 15:36:52.571491+02	2026-01-11 15:36:52.571501+02	f	1	3	3	18
785	{"source": "Municipal Supply", "wastewater_m3": 564.0, "co2e_emissions": 228.42, "consumption_m3": 664, "reporting_year": 2022, "reporting_month": "May"}	2026-01-11 15:36:52.575006+02	2026-01-11 15:36:52.575019+02	f	1	3	3	18
786	{"source": "Municipal Supply", "wastewater_m3": 577.0, "co2e_emissions": 233.58, "consumption_m3": 679, "reporting_year": 2022, "reporting_month": "June"}	2026-01-11 15:36:52.580576+02	2026-01-11 15:36:52.580594+02	f	1	3	3	18
787	{"source": "Municipal Supply", "wastewater_m3": 853.0, "co2e_emissions": 345.03, "consumption_m3": 1003, "reporting_year": 2022, "reporting_month": "July"}	2026-01-11 15:36:52.585485+02	2026-01-11 15:36:52.5855+02	f	1	3	3	18
788	{"source": "Municipal Supply", "wastewater_m3": 857.0, "co2e_emissions": 346.75, "consumption_m3": 1008, "reporting_year": 2022, "reporting_month": "August"}	2026-01-11 15:36:52.58919+02	2026-01-11 15:36:52.589203+02	f	1	3	3	18
789	{"source": "Municipal Supply", "wastewater_m3": 819.0, "co2e_emissions": 331.27, "consumption_m3": 963, "reporting_year": 2022, "reporting_month": "September"}	2026-01-11 15:36:52.593+02	2026-01-11 15:36:52.593018+02	f	1	3	3	18
790	{"source": "Municipal Supply", "wastewater_m3": 904.0, "co2e_emissions": 366.02, "consumption_m3": 1064, "reporting_year": 2022, "reporting_month": "October"}	2026-01-11 15:36:52.596975+02	2026-01-11 15:36:52.596989+02	f	1	3	3	18
791	{"source": "Municipal Supply", "wastewater_m3": 1163.0, "co2e_emissions": 470.59, "consumption_m3": 1368, "reporting_year": 2022, "reporting_month": "November"}	2026-01-11 15:36:52.600348+02	2026-01-11 15:36:52.60036+02	f	1	3	3	18
792	{"source": "Municipal Supply", "wastewater_m3": 1119.0, "co2e_emissions": 453.05, "consumption_m3": 1317, "reporting_year": 2022, "reporting_month": "December"}	2026-01-11 15:36:52.605669+02	2026-01-11 15:36:52.605682+02	f	1	3	3	18
793	{"source": "Municipal Supply", "wastewater_m3": 1167.0, "co2e_emissions": 472.31, "consumption_m3": 1373, "reporting_year": 2023, "reporting_month": "January"}	2026-01-11 15:36:52.609517+02	2026-01-11 15:36:52.609533+02	f	1	3	3	18
794	{"source": "Municipal Supply", "wastewater_m3": 1169.0, "co2e_emissions": 473.0, "consumption_m3": 1375, "reporting_year": 2023, "reporting_month": "February"}	2026-01-11 15:36:52.613208+02	2026-01-11 15:36:52.613222+02	f	1	3	3	18
795	{"source": "Municipal Supply", "wastewater_m3": 1088.0, "co2e_emissions": 440.32, "consumption_m3": 1280, "reporting_year": 2023, "reporting_month": "March"}	2026-01-11 15:36:52.616907+02	2026-01-11 15:36:52.616921+02	f	1	3	3	18
796	{"source": "Municipal Supply", "wastewater_m3": 1088.0, "co2e_emissions": 440.32, "consumption_m3": 1280, "reporting_year": 2023, "reporting_month": "April"}	2026-01-11 15:36:52.620357+02	2026-01-11 15:36:52.62037+02	f	1	3	3	18
797	{"source": "Municipal Supply", "wastewater_m3": 601.0, "co2e_emissions": 243.21, "consumption_m3": 707, "reporting_year": 2023, "reporting_month": "May"}	2026-01-11 15:36:52.624+02	2026-01-11 15:36:52.624015+02	f	1	3	3	18
798	{"source": "Municipal Supply", "wastewater_m3": 601.0, "co2e_emissions": 243.21, "consumption_m3": 707, "reporting_year": 2023, "reporting_month": "June"}	2026-01-11 15:36:52.627661+02	2026-01-11 15:36:52.627676+02	f	1	3	3	18
799	{"source": "Municipal Supply", "wastewater_m3": 814.0, "co2e_emissions": 329.55, "consumption_m3": 958, "reporting_year": 2023, "reporting_month": "July"}	2026-01-11 15:36:52.631418+02	2026-01-11 15:36:52.631431+02	f	1	3	3	18
800	{"source": "Municipal Supply", "wastewater_m3": 815.0, "co2e_emissions": 329.9, "consumption_m3": 959, "reporting_year": 2023, "reporting_month": "August"}	2026-01-11 15:36:52.63465+02	2026-01-11 15:36:52.634662+02	f	1	3	3	18
801	{"source": "Municipal Supply", "wastewater_m3": 833.0, "co2e_emissions": 337.12, "consumption_m3": 980, "reporting_year": 2023, "reporting_month": "September"}	2026-01-11 15:36:52.638042+02	2026-01-11 15:36:52.638066+02	f	1	3	3	18
802	{"source": "Municipal Supply", "wastewater_m3": 833.0, "co2e_emissions": 337.12, "consumption_m3": 980, "reporting_year": 2023, "reporting_month": "October"}	2026-01-11 15:36:52.647023+02	2026-01-11 15:36:52.647037+02	f	1	3	3	18
803	{"source": "Municipal Supply", "wastewater_m3": 1112.0, "co2e_emissions": 449.95, "consumption_m3": 1308, "reporting_year": 2023, "reporting_month": "November"}	2026-01-11 15:36:52.671929+02	2026-01-11 15:36:52.671945+02	f	1	3	3	18
804	{"source": "Municipal Supply", "wastewater_m3": 1112.0, "co2e_emissions": 449.95, "consumption_m3": 1308, "reporting_year": 2023, "reporting_month": "December"}	2026-01-11 15:36:52.675514+02	2026-01-11 15:36:52.675531+02	f	1	3	3	18
805	{"source": "Municipal Supply", "wastewater_m3": 722.0, "co2e_emissions": 292.4, "consumption_m3": 850, "reporting_year": 2024, "reporting_month": "January"}	2026-01-11 15:36:52.679988+02	2026-01-11 15:36:52.679998+02	f	1	3	3	18
806	{"source": "Municipal Supply", "wastewater_m3": 722.0, "co2e_emissions": 292.4, "consumption_m3": 850, "reporting_year": 2024, "reporting_month": "February"}	2026-01-11 15:36:52.683751+02	2026-01-11 15:36:52.683761+02	f	1	3	3	18
807	{"source": "Municipal Supply", "wastewater_m3": 699.0, "co2e_emissions": 282.77, "consumption_m3": 822, "reporting_year": 2024, "reporting_month": "March"}	2026-01-11 15:36:52.687581+02	2026-01-11 15:36:52.687598+02	f	1	3	3	18
808	{"source": "Municipal Supply", "wastewater_m3": 700.0, "co2e_emissions": 283.46, "consumption_m3": 824, "reporting_year": 2024, "reporting_month": "April"}	2026-01-11 15:36:52.691283+02	2026-01-11 15:36:52.691295+02	f	1	3	3	18
809	{"source": "Municipal Supply", "wastewater_m3": 701.0, "co2e_emissions": 283.8, "consumption_m3": 825, "reporting_year": 2024, "reporting_month": "May"}	2026-01-11 15:36:52.695032+02	2026-01-11 15:36:52.695046+02	f	1	3	3	18
810	{"source": "Municipal Supply", "wastewater_m3": 702.0, "co2e_emissions": 284.14, "consumption_m3": 826, "reporting_year": 2024, "reporting_month": "June"}	2026-01-11 15:36:52.700194+02	2026-01-11 15:36:52.700211+02	f	1	3	3	18
811	{"source": "Municipal Supply", "wastewater_m3": 941.0, "co2e_emissions": 380.81, "consumption_m3": 1107, "reporting_year": 2024, "reporting_month": "July"}	2026-01-11 15:36:52.704315+02	2026-01-11 15:36:52.704329+02	f	1	3	3	18
812	{"source": "Municipal Supply", "wastewater_m3": 823.0, "co2e_emissions": 332.99, "consumption_m3": 968, "reporting_year": 2024, "reporting_month": "August"}	2026-01-11 15:36:52.708135+02	2026-01-11 15:36:52.708148+02	f	1	3	3	18
813	{"source": "Municipal Supply", "wastewater_m3": 901.0, "co2e_emissions": 364.64, "consumption_m3": 1060, "reporting_year": 2024, "reporting_month": "September"}	2026-01-11 15:36:52.711789+02	2026-01-11 15:36:52.711802+02	f	1	3	3	18
814	{"source": "Municipal Supply", "wastewater_m3": 887.0, "co2e_emissions": 359.14, "consumption_m3": 1044, "reporting_year": 2024, "reporting_month": "October"}	2026-01-11 15:36:52.71655+02	2026-01-11 15:36:52.716567+02	f	1	3	3	18
815	{"source": "Municipal Supply", "wastewater_m3": 1155.0, "co2e_emissions": 467.5, "consumption_m3": 1359, "reporting_year": 2024, "reporting_month": "November"}	2026-01-11 15:36:52.720526+02	2026-01-11 15:36:52.720542+02	f	1	3	3	18
816	{"source": "Municipal Supply", "wastewater_m3": 1269.0, "co2e_emissions": 513.59, "consumption_m3": 1493, "reporting_year": 2024, "reporting_month": "December"}	2026-01-11 15:36:52.723967+02	2026-01-11 15:36:52.723981+02	f	1	3	3	18
817	{"total_km": 1320000, "headcount": 120, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 277200.0, "reporting_year": 2020, "transport_mode": "Private Car", "avg_distance_km": 25}	2026-01-11 15:36:52.778863+02	2026-01-11 15:36:52.778878+02	f	1	3	3	19
818	{"total_km": 1056000, "headcount": 80, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 93984.0, "reporting_year": 2020, "transport_mode": "University Bus", "avg_distance_km": 30}	2026-01-11 15:36:52.7825+02	2026-01-11 15:36:52.782518+02	f	1	3	3	19
867	{"waste_type": "General Waste", "quantity_kg": 2345, "co2e_emissions": 1360.1, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:53.035396+02	2026-01-11 15:36:53.035409+02	f	1	3	3	20
819	{"total_km": 352000, "headcount": 40, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 31328.0, "reporting_year": 2020, "transport_mode": "Public Bus", "avg_distance_km": 20}	2026-01-11 15:36:52.787572+02	2026-01-11 15:36:52.787586+02	f	1	3	3	19
820	{"total_km": 1425600, "headcount": 180, "working_days": 180, "commuter_type": "Faculty", "co2e_emissions": 299376.0, "reporting_year": 2020, "transport_mode": "Private Car", "avg_distance_km": 22}	2026-01-11 15:36:52.791538+02	2026-01-11 15:36:52.791552+02	f	1	3	3	19
821	{"total_km": 302400, "headcount": 30, "working_days": 180, "commuter_type": "Faculty", "co2e_emissions": 26913.6, "reporting_year": 2020, "transport_mode": "University Bus", "avg_distance_km": 28}	2026-01-11 15:36:52.795334+02	2026-01-11 15:36:52.79535+02	f	1	3	3	19
822	{"total_km": 8960000, "headcount": 800, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 797440.0, "reporting_year": 2020, "transport_mode": "University Bus", "avg_distance_km": 35}	2026-01-11 15:36:52.798909+02	2026-01-11 15:36:52.798925+02	f	1	3	3	19
823	{"total_km": 2304000, "headcount": 400, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 483840.0, "reporting_year": 2020, "transport_mode": "Private Car", "avg_distance_km": 18}	2026-01-11 15:36:52.802501+02	2026-01-11 15:36:52.802516+02	f	1	3	3	19
824	{"total_km": 4800000, "headcount": 600, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 427200.0, "reporting_year": 2020, "transport_mode": "Public Bus", "avg_distance_km": 25}	2026-01-11 15:36:52.808569+02	2026-01-11 15:36:52.808585+02	f	1	3	3	19
825	{"total_km": 1920000, "headcount": 200, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 78720.0, "reporting_year": 2020, "transport_mode": "Metro", "avg_distance_km": 30}	2026-01-11 15:36:52.814094+02	2026-01-11 15:36:52.81411+02	f	1	3	3	19
826	{"total_km": 960000, "headcount": 150, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 100800.0, "reporting_year": 2020, "transport_mode": "Carpool", "avg_distance_km": 20}	2026-01-11 15:36:52.817698+02	2026-01-11 15:36:52.817712+02	f	1	3	3	19
827	{"total_km": 1320000, "headcount": 120, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 277200.0, "reporting_year": 2021, "transport_mode": "Private Car", "avg_distance_km": 25}	2026-01-11 15:36:52.82114+02	2026-01-11 15:36:52.821152+02	f	1	3	3	19
828	{"total_km": 1095600, "headcount": 83, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 97508.4, "reporting_year": 2021, "transport_mode": "University Bus", "avg_distance_km": 30}	2026-01-11 15:36:52.824706+02	2026-01-11 15:36:52.824729+02	f	1	3	3	19
829	{"total_km": 360800, "headcount": 41, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 32111.2, "reporting_year": 2021, "transport_mode": "Public Bus", "avg_distance_km": 20}	2026-01-11 15:36:52.829922+02	2026-01-11 15:36:52.829938+02	f	1	3	3	19
830	{"total_km": 1433520, "headcount": 181, "working_days": 180, "commuter_type": "Faculty", "co2e_emissions": 301039.2, "reporting_year": 2021, "transport_mode": "Private Car", "avg_distance_km": 22}	2026-01-11 15:36:52.835172+02	2026-01-11 15:36:52.835188+02	f	1	3	3	19
831	{"total_km": 302400, "headcount": 30, "working_days": 180, "commuter_type": "Faculty", "co2e_emissions": 26913.6, "reporting_year": 2021, "transport_mode": "University Bus", "avg_distance_km": 28}	2026-01-11 15:36:52.840407+02	2026-01-11 15:36:52.840425+02	f	1	3	3	19
832	{"total_km": 9408000, "headcount": 840, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 837312.0, "reporting_year": 2021, "transport_mode": "University Bus", "avg_distance_km": 35}	2026-01-11 15:36:52.844406+02	2026-01-11 15:36:52.844423+02	f	1	3	3	19
833	{"total_km": 2321280, "headcount": 403, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 487468.8, "reporting_year": 2021, "transport_mode": "Private Car", "avg_distance_km": 18}	2026-01-11 15:36:52.848134+02	2026-01-11 15:36:52.848148+02	f	1	3	3	19
834	{"total_km": 5040000, "headcount": 630, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 448560.0, "reporting_year": 2021, "transport_mode": "Public Bus", "avg_distance_km": 25}	2026-01-11 15:36:52.851994+02	2026-01-11 15:36:52.852009+02	f	1	3	3	19
835	{"total_km": 2016000, "headcount": 210, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 82656.0, "reporting_year": 2021, "transport_mode": "Metro", "avg_distance_km": 30}	2026-01-11 15:36:52.85605+02	2026-01-11 15:36:52.856072+02	f	1	3	3	19
836	{"total_km": 985600, "headcount": 154, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 103488.0, "reporting_year": 2021, "transport_mode": "Carpool", "avg_distance_km": 20}	2026-01-11 15:36:52.862179+02	2026-01-11 15:36:52.862199+02	f	1	3	3	19
837	{"total_km": 1331000, "headcount": 121, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 279510.0, "reporting_year": 2022, "transport_mode": "Private Car", "avg_distance_km": 25}	2026-01-11 15:36:52.866027+02	2026-01-11 15:36:52.866042+02	f	1	3	3	19
838	{"total_km": 1148400, "headcount": 87, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 102207.6, "reporting_year": 2022, "transport_mode": "University Bus", "avg_distance_km": 30}	2026-01-11 15:36:52.870818+02	2026-01-11 15:36:52.870834+02	f	1	3	3	19
839	{"total_km": 378400, "headcount": 43, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 33677.6, "reporting_year": 2022, "transport_mode": "Public Bus", "avg_distance_km": 20}	2026-01-11 15:36:52.875112+02	2026-01-11 15:36:52.875127+02	f	1	3	3	19
840	{"total_km": 1441440, "headcount": 182, "working_days": 180, "commuter_type": "Faculty", "co2e_emissions": 302702.4, "reporting_year": 2022, "transport_mode": "Private Car", "avg_distance_km": 22}	2026-01-11 15:36:52.879298+02	2026-01-11 15:36:52.879312+02	f	1	3	3	19
841	{"total_km": 322560, "headcount": 32, "working_days": 180, "commuter_type": "Faculty", "co2e_emissions": 28707.84, "reporting_year": 2022, "transport_mode": "University Bus", "avg_distance_km": 28}	2026-01-11 15:36:52.882958+02	2026-01-11 15:36:52.882969+02	f	1	3	3	19
842	{"total_km": 9867200, "headcount": 881, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 878180.8, "reporting_year": 2022, "transport_mode": "University Bus", "avg_distance_km": 35}	2026-01-11 15:36:52.889262+02	2026-01-11 15:36:52.889278+02	f	1	3	3	19
843	{"total_km": 2344320, "headcount": 407, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 492307.2, "reporting_year": 2022, "transport_mode": "Private Car", "avg_distance_km": 18}	2026-01-11 15:36:52.893114+02	2026-01-11 15:36:52.893125+02	f	1	3	3	19
844	{"total_km": 5288000, "headcount": 661, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 470632.0, "reporting_year": 2022, "transport_mode": "Public Bus", "avg_distance_km": 25}	2026-01-11 15:36:52.896633+02	2026-01-11 15:36:52.896647+02	f	1	3	3	19
845	{"total_km": 2112000, "headcount": 220, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 86592.0, "reporting_year": 2022, "transport_mode": "Metro", "avg_distance_km": 30}	2026-01-11 15:36:52.900055+02	2026-01-11 15:36:52.900067+02	f	1	3	3	19
846	{"total_km": 1017600, "headcount": 159, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 106848.0, "reporting_year": 2022, "transport_mode": "Carpool", "avg_distance_km": 20}	2026-01-11 15:36:52.903817+02	2026-01-11 15:36:52.903833+02	f	1	3	3	19
847	{"total_km": 1342000, "headcount": 122, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 281820.0, "reporting_year": 2023, "transport_mode": "Private Car", "avg_distance_km": 25}	2026-01-11 15:36:52.908652+02	2026-01-11 15:36:52.908666+02	f	1	3	3	19
848	{"total_km": 1214400, "headcount": 92, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 108081.6, "reporting_year": 2023, "transport_mode": "University Bus", "avg_distance_km": 30}	2026-01-11 15:36:52.912426+02	2026-01-11 15:36:52.912442+02	f	1	3	3	19
849	{"total_km": 396000, "headcount": 45, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 35244.0, "reporting_year": 2023, "transport_mode": "Public Bus", "avg_distance_km": 20}	2026-01-11 15:36:52.916209+02	2026-01-11 15:36:52.916225+02	f	1	3	3	19
850	{"total_km": 1457280, "headcount": 184, "working_days": 180, "commuter_type": "Faculty", "co2e_emissions": 306028.8, "reporting_year": 2023, "transport_mode": "Private Car", "avg_distance_km": 22}	2026-01-11 15:36:52.920145+02	2026-01-11 15:36:52.920163+02	f	1	3	3	19
851	{"total_km": 332640, "headcount": 33, "working_days": 180, "commuter_type": "Faculty", "co2e_emissions": 29604.96, "reporting_year": 2023, "transport_mode": "University Bus", "avg_distance_km": 28}	2026-01-11 15:36:52.924045+02	2026-01-11 15:36:52.92406+02	f	1	3	3	19
852	{"total_km": 10348800, "headcount": 924, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 921043.2, "reporting_year": 2023, "transport_mode": "University Bus", "avg_distance_km": 35}	2026-01-11 15:36:52.92756+02	2026-01-11 15:36:52.927572+02	f	1	3	3	19
853	{"total_km": 2355840, "headcount": 409, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 494726.4, "reporting_year": 2023, "transport_mode": "Private Car", "avg_distance_km": 18}	2026-01-11 15:36:52.931425+02	2026-01-11 15:36:52.931442+02	f	1	3	3	19
854	{"total_km": 5544000, "headcount": 693, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 493416.0, "reporting_year": 2023, "transport_mode": "Public Bus", "avg_distance_km": 25}	2026-01-11 15:36:52.936655+02	2026-01-11 15:36:52.936672+02	f	1	3	3	19
855	{"total_km": 2217600, "headcount": 231, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 90921.6, "reporting_year": 2023, "transport_mode": "Metro", "avg_distance_km": 30}	2026-01-11 15:36:52.940452+02	2026-01-11 15:36:52.940466+02	f	1	3	3	19
856	{"total_km": 1043200, "headcount": 163, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 109536.0, "reporting_year": 2023, "transport_mode": "Carpool", "avg_distance_km": 20}	2026-01-11 15:36:52.944031+02	2026-01-11 15:36:52.944053+02	f	1	3	3	19
857	{"total_km": 1353000, "headcount": 123, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 284130.0, "reporting_year": 2024, "transport_mode": "Private Car", "avg_distance_km": 25}	2026-01-11 15:36:52.94761+02	2026-01-11 15:36:52.947626+02	f	1	3	3	19
858	{"total_km": 1267200, "headcount": 96, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 112780.8, "reporting_year": 2024, "transport_mode": "University Bus", "avg_distance_km": 30}	2026-01-11 15:36:52.952659+02	2026-01-11 15:36:52.952678+02	f	1	3	3	19
859	{"total_km": 413600, "headcount": 47, "working_days": 220, "commuter_type": "Staff", "co2e_emissions": 36810.4, "reporting_year": 2024, "transport_mode": "Public Bus", "avg_distance_km": 20}	2026-01-11 15:36:52.95742+02	2026-01-11 15:36:52.957434+02	f	1	3	3	19
860	{"total_km": 1457280, "headcount": 184, "working_days": 180, "commuter_type": "Faculty", "co2e_emissions": 306028.8, "reporting_year": 2024, "transport_mode": "Private Car", "avg_distance_km": 22}	2026-01-11 15:36:52.961068+02	2026-01-11 15:36:52.961082+02	f	1	3	3	19
861	{"total_km": 352800, "headcount": 35, "working_days": 180, "commuter_type": "Faculty", "co2e_emissions": 31399.2, "reporting_year": 2024, "transport_mode": "University Bus", "avg_distance_km": 28}	2026-01-11 15:36:52.966818+02	2026-01-11 15:36:52.966833+02	f	1	3	3	19
862	{"total_km": 10830400, "headcount": 967, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 963905.6, "reporting_year": 2024, "transport_mode": "University Bus", "avg_distance_km": 35}	2026-01-11 15:36:52.970363+02	2026-01-11 15:36:52.970377+02	f	1	3	3	19
863	{"total_km": 2373120, "headcount": 412, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 498355.2, "reporting_year": 2024, "transport_mode": "Private Car", "avg_distance_km": 18}	2026-01-11 15:36:52.973853+02	2026-01-11 15:36:52.973866+02	f	1	3	3	19
864	{"total_km": 5800000, "headcount": 725, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 516200.0, "reporting_year": 2024, "transport_mode": "Public Bus", "avg_distance_km": 25}	2026-01-11 15:36:52.980064+02	2026-01-11 15:36:52.980082+02	f	1	3	3	19
865	{"total_km": 2313600, "headcount": 241, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 94857.6, "reporting_year": 2024, "transport_mode": "Metro", "avg_distance_km": 30}	2026-01-11 15:36:52.984107+02	2026-01-11 15:36:52.984124+02	f	1	3	3	19
866	{"total_km": 1075200, "headcount": 168, "working_days": 160, "commuter_type": "Student", "co2e_emissions": 112896.0, "reporting_year": 2024, "transport_mode": "Carpool", "avg_distance_km": 20}	2026-01-11 15:36:52.987966+02	2026-01-11 15:36:52.98798+02	f	1	3	3	19
868	{"waste_type": "Paper/Cardboard", "quantity_kg": 718, "co2e_emissions": 14.36, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "January"}	2026-01-11 15:36:53.038979+02	2026-01-11 15:36:53.038993+02	f	1	3	3	20
869	{"waste_type": "Paper/Cardboard", "quantity_kg": 355, "co2e_emissions": 205.9, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:53.042602+02	2026-01-11 15:36:53.042621+02	f	1	3	3	20
870	{"waste_type": "Plastic", "quantity_kg": 186, "co2e_emissions": 3.72, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "January"}	2026-01-11 15:36:53.046375+02	2026-01-11 15:36:53.046389+02	f	1	3	3	20
871	{"waste_type": "Plastic", "quantity_kg": 252, "co2e_emissions": 146.16, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:53.052467+02	2026-01-11 15:36:53.052484+02	f	1	3	3	20
872	{"waste_type": "Food Waste", "quantity_kg": 492, "co2e_emissions": 49.2, "reporting_year": 2020, "disposal_method": "Composted", "reporting_month": "January"}	2026-01-11 15:36:53.055794+02	2026-01-11 15:36:53.055806+02	f	1	3	3	20
873	{"waste_type": "Food Waste", "quantity_kg": 804, "co2e_emissions": 466.32, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:53.059353+02	2026-01-11 15:36:53.059369+02	f	1	3	3	20
874	{"waste_type": "E-Waste", "quantity_kg": 48, "co2e_emissions": 4.8, "reporting_year": 2020, "disposal_method": "Special Treatment", "reporting_month": "January"}	2026-01-11 15:36:53.065705+02	2026-01-11 15:36:53.065721+02	f	1	3	3	20
875	{"waste_type": "General Waste", "quantity_kg": 2271, "co2e_emissions": 1317.18, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:53.069697+02	2026-01-11 15:36:53.06971+02	f	1	3	3	20
876	{"waste_type": "Paper/Cardboard", "quantity_kg": 809, "co2e_emissions": 16.18, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "February"}	2026-01-11 15:36:53.075671+02	2026-01-11 15:36:53.075689+02	f	1	3	3	20
877	{"waste_type": "Paper/Cardboard", "quantity_kg": 365, "co2e_emissions": 211.7, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:53.0858+02	2026-01-11 15:36:53.085816+02	f	1	3	3	20
878	{"waste_type": "Plastic", "quantity_kg": 194, "co2e_emissions": 3.88, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "February"}	2026-01-11 15:36:53.089818+02	2026-01-11 15:36:53.089839+02	f	1	3	3	20
879	{"waste_type": "Plastic", "quantity_kg": 276, "co2e_emissions": 160.08, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:53.093587+02	2026-01-11 15:36:53.093602+02	f	1	3	3	20
880	{"waste_type": "Food Waste", "quantity_kg": 563, "co2e_emissions": 56.3, "reporting_year": 2020, "disposal_method": "Composted", "reporting_month": "February"}	2026-01-11 15:36:53.09733+02	2026-01-11 15:36:53.097342+02	f	1	3	3	20
881	{"waste_type": "Food Waste", "quantity_kg": 829, "co2e_emissions": 480.82, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:53.102166+02	2026-01-11 15:36:53.10218+02	f	1	3	3	20
882	{"waste_type": "E-Waste", "quantity_kg": 45, "co2e_emissions": 4.5, "reporting_year": 2020, "disposal_method": "Special Treatment", "reporting_month": "February"}	2026-01-11 15:36:53.105873+02	2026-01-11 15:36:53.105888+02	f	1	3	3	20
883	{"waste_type": "General Waste", "quantity_kg": 2549, "co2e_emissions": 1478.42, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:53.110381+02	2026-01-11 15:36:53.110394+02	f	1	3	3	20
884	{"waste_type": "Paper/Cardboard", "quantity_kg": 759, "co2e_emissions": 15.18, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "March"}	2026-01-11 15:36:53.114126+02	2026-01-11 15:36:53.114141+02	f	1	3	3	20
885	{"waste_type": "Paper/Cardboard", "quantity_kg": 416, "co2e_emissions": 241.28, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:53.117935+02	2026-01-11 15:36:53.11795+02	f	1	3	3	20
886	{"waste_type": "Plastic", "quantity_kg": 182, "co2e_emissions": 3.64, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "March"}	2026-01-11 15:36:53.121823+02	2026-01-11 15:36:53.121838+02	f	1	3	3	20
887	{"waste_type": "Plastic", "quantity_kg": 297, "co2e_emissions": 172.26, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:53.125539+02	2026-01-11 15:36:53.125581+02	f	1	3	3	20
888	{"waste_type": "Food Waste", "quantity_kg": 553, "co2e_emissions": 55.3, "reporting_year": 2020, "disposal_method": "Composted", "reporting_month": "March"}	2026-01-11 15:36:53.130556+02	2026-01-11 15:36:53.130572+02	f	1	3	3	20
889	{"waste_type": "Food Waste", "quantity_kg": 854, "co2e_emissions": 495.32, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:53.140277+02	2026-01-11 15:36:53.140293+02	f	1	3	3	20
890	{"waste_type": "E-Waste", "quantity_kg": 49, "co2e_emissions": 4.9, "reporting_year": 2020, "disposal_method": "Special Treatment", "reporting_month": "March"}	2026-01-11 15:36:53.143875+02	2026-01-11 15:36:53.14389+02	f	1	3	3	20
891	{"waste_type": "General Waste", "quantity_kg": 2318, "co2e_emissions": 1344.44, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:53.147883+02	2026-01-11 15:36:53.1479+02	f	1	3	3	20
892	{"waste_type": "Paper/Cardboard", "quantity_kg": 746, "co2e_emissions": 14.92, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "April"}	2026-01-11 15:36:53.153051+02	2026-01-11 15:36:53.153067+02	f	1	3	3	20
893	{"waste_type": "Paper/Cardboard", "quantity_kg": 361, "co2e_emissions": 209.38, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:53.156952+02	2026-01-11 15:36:53.156968+02	f	1	3	3	20
894	{"waste_type": "Plastic", "quantity_kg": 195, "co2e_emissions": 3.9, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "April"}	2026-01-11 15:36:53.16074+02	2026-01-11 15:36:53.160755+02	f	1	3	3	20
895	{"waste_type": "Plastic", "quantity_kg": 278, "co2e_emissions": 161.24, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:53.164187+02	2026-01-11 15:36:53.164201+02	f	1	3	3	20
896	{"waste_type": "Food Waste", "quantity_kg": 629, "co2e_emissions": 62.9, "reporting_year": 2020, "disposal_method": "Composted", "reporting_month": "April"}	2026-01-11 15:36:53.168008+02	2026-01-11 15:36:53.168025+02	f	1	3	3	20
897	{"waste_type": "Food Waste", "quantity_kg": 950, "co2e_emissions": 551.0, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:53.173949+02	2026-01-11 15:36:53.173964+02	f	1	3	3	20
898	{"waste_type": "E-Waste", "quantity_kg": 46, "co2e_emissions": 4.6, "reporting_year": 2020, "disposal_method": "Special Treatment", "reporting_month": "April"}	2026-01-11 15:36:53.177852+02	2026-01-11 15:36:53.17787+02	f	1	3	3	20
899	{"waste_type": "General Waste", "quantity_kg": 2043, "co2e_emissions": 1184.94, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:53.182131+02	2026-01-11 15:36:53.18215+02	f	1	3	3	20
900	{"waste_type": "Paper/Cardboard", "quantity_kg": 776, "co2e_emissions": 15.52, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "May"}	2026-01-11 15:36:53.190013+02	2026-01-11 15:36:53.190029+02	f	1	3	3	20
901	{"waste_type": "Paper/Cardboard", "quantity_kg": 395, "co2e_emissions": 229.1, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:53.19474+02	2026-01-11 15:36:53.194751+02	f	1	3	3	20
902	{"waste_type": "Plastic", "quantity_kg": 168, "co2e_emissions": 3.36, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "May"}	2026-01-11 15:36:53.198459+02	2026-01-11 15:36:53.198475+02	f	1	3	3	20
903	{"waste_type": "Plastic", "quantity_kg": 258, "co2e_emissions": 149.64, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:53.202095+02	2026-01-11 15:36:53.202109+02	f	1	3	3	20
904	{"waste_type": "Food Waste", "quantity_kg": 578, "co2e_emissions": 57.8, "reporting_year": 2020, "disposal_method": "Composted", "reporting_month": "May"}	2026-01-11 15:36:53.205609+02	2026-01-11 15:36:53.205624+02	f	1	3	3	20
905	{"waste_type": "Food Waste", "quantity_kg": 797, "co2e_emissions": 462.26, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:53.209144+02	2026-01-11 15:36:53.209157+02	f	1	3	3	20
906	{"waste_type": "E-Waste", "quantity_kg": 46, "co2e_emissions": 4.6, "reporting_year": 2020, "disposal_method": "Special Treatment", "reporting_month": "May"}	2026-01-11 15:36:53.214341+02	2026-01-11 15:36:53.214356+02	f	1	3	3	20
907	{"waste_type": "General Waste", "quantity_kg": 1684, "co2e_emissions": 976.72, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:53.218142+02	2026-01-11 15:36:53.218156+02	f	1	3	3	20
908	{"waste_type": "Paper/Cardboard", "quantity_kg": 568, "co2e_emissions": 11.36, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "June"}	2026-01-11 15:36:53.221538+02	2026-01-11 15:36:53.221552+02	f	1	3	3	20
909	{"waste_type": "Paper/Cardboard", "quantity_kg": 306, "co2e_emissions": 177.48, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:53.224757+02	2026-01-11 15:36:53.224767+02	f	1	3	3	20
910	{"waste_type": "Plastic", "quantity_kg": 142, "co2e_emissions": 2.84, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "June"}	2026-01-11 15:36:53.231296+02	2026-01-11 15:36:53.23131+02	f	1	3	3	20
911	{"waste_type": "Plastic", "quantity_kg": 193, "co2e_emissions": 111.94, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:53.234949+02	2026-01-11 15:36:53.234969+02	f	1	3	3	20
912	{"waste_type": "Food Waste", "quantity_kg": 459, "co2e_emissions": 45.9, "reporting_year": 2020, "disposal_method": "Composted", "reporting_month": "June"}	2026-01-11 15:36:53.238296+02	2026-01-11 15:36:53.23831+02	f	1	3	3	20
913	{"waste_type": "Food Waste", "quantity_kg": 675, "co2e_emissions": 391.5, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:53.241698+02	2026-01-11 15:36:53.241711+02	f	1	3	3	20
914	{"waste_type": "E-Waste", "quantity_kg": 35, "co2e_emissions": 3.5, "reporting_year": 2020, "disposal_method": "Special Treatment", "reporting_month": "June"}	2026-01-11 15:36:53.245176+02	2026-01-11 15:36:53.245193+02	f	1	3	3	20
915	{"waste_type": "General Waste", "quantity_kg": 929, "co2e_emissions": 538.82, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:53.251834+02	2026-01-11 15:36:53.251848+02	f	1	3	3	20
916	{"waste_type": "Paper/Cardboard", "quantity_kg": 341, "co2e_emissions": 6.82, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "July"}	2026-01-11 15:36:53.25538+02	2026-01-11 15:36:53.255395+02	f	1	3	3	20
917	{"waste_type": "Paper/Cardboard", "quantity_kg": 160, "co2e_emissions": 92.8, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:53.260847+02	2026-01-11 15:36:53.260863+02	f	1	3	3	20
918	{"waste_type": "Plastic", "quantity_kg": 74, "co2e_emissions": 1.48, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "July"}	2026-01-11 15:36:53.264493+02	2026-01-11 15:36:53.264507+02	f	1	3	3	20
919	{"waste_type": "Plastic", "quantity_kg": 124, "co2e_emissions": 71.92, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:53.267976+02	2026-01-11 15:36:53.267989+02	f	1	3	3	20
920	{"waste_type": "Food Waste", "quantity_kg": 238, "co2e_emissions": 23.8, "reporting_year": 2020, "disposal_method": "Composted", "reporting_month": "July"}	2026-01-11 15:36:53.272634+02	2026-01-11 15:36:53.272647+02	f	1	3	3	20
921	{"waste_type": "Food Waste", "quantity_kg": 394, "co2e_emissions": 228.52, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:53.278304+02	2026-01-11 15:36:53.278319+02	f	1	3	3	20
922	{"waste_type": "E-Waste", "quantity_kg": 20, "co2e_emissions": 2.0, "reporting_year": 2020, "disposal_method": "Special Treatment", "reporting_month": "July"}	2026-01-11 15:36:53.281778+02	2026-01-11 15:36:53.281791+02	f	1	3	3	20
923	{"waste_type": "General Waste", "quantity_kg": 717, "co2e_emissions": 415.86, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:53.285336+02	2026-01-11 15:36:53.285351+02	f	1	3	3	20
924	{"waste_type": "Paper/Cardboard", "quantity_kg": 249, "co2e_emissions": 4.98, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "August"}	2026-01-11 15:36:53.288768+02	2026-01-11 15:36:53.288782+02	f	1	3	3	20
925	{"waste_type": "Paper/Cardboard", "quantity_kg": 115, "co2e_emissions": 66.7, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:53.292437+02	2026-01-11 15:36:53.292453+02	f	1	3	3	20
926	{"waste_type": "Plastic", "quantity_kg": 55, "co2e_emissions": 1.1, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "August"}	2026-01-11 15:36:53.297414+02	2026-01-11 15:36:53.297427+02	f	1	3	3	20
927	{"waste_type": "Plastic", "quantity_kg": 91, "co2e_emissions": 52.78, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:53.302181+02	2026-01-11 15:36:53.302195+02	f	1	3	3	20
928	{"waste_type": "Food Waste", "quantity_kg": 169, "co2e_emissions": 16.9, "reporting_year": 2020, "disposal_method": "Composted", "reporting_month": "August"}	2026-01-11 15:36:53.305842+02	2026-01-11 15:36:53.30586+02	f	1	3	3	20
929	{"waste_type": "Food Waste", "quantity_kg": 290, "co2e_emissions": 168.2, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:53.309634+02	2026-01-11 15:36:53.309649+02	f	1	3	3	20
930	{"waste_type": "E-Waste", "quantity_kg": 13, "co2e_emissions": 1.3, "reporting_year": 2020, "disposal_method": "Special Treatment", "reporting_month": "August"}	2026-01-11 15:36:53.312957+02	2026-01-11 15:36:53.312971+02	f	1	3	3	20
931	{"waste_type": "General Waste", "quantity_kg": 2500, "co2e_emissions": 1450.0, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:53.316606+02	2026-01-11 15:36:53.316616+02	f	1	3	3	20
932	{"waste_type": "Paper/Cardboard", "quantity_kg": 831, "co2e_emissions": 16.62, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "September"}	2026-01-11 15:36:53.321098+02	2026-01-11 15:36:53.321119+02	f	1	3	3	20
933	{"waste_type": "Paper/Cardboard", "quantity_kg": 342, "co2e_emissions": 198.36, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:53.325461+02	2026-01-11 15:36:53.325478+02	f	1	3	3	20
934	{"waste_type": "Plastic", "quantity_kg": 186, "co2e_emissions": 3.72, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "September"}	2026-01-11 15:36:53.328945+02	2026-01-11 15:36:53.32896+02	f	1	3	3	20
935	{"waste_type": "Plastic", "quantity_kg": 301, "co2e_emissions": 174.58, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:53.332731+02	2026-01-11 15:36:53.332747+02	f	1	3	3	20
936	{"waste_type": "Food Waste", "quantity_kg": 616, "co2e_emissions": 61.6, "reporting_year": 2020, "disposal_method": "Composted", "reporting_month": "September"}	2026-01-11 15:36:53.336425+02	2026-01-11 15:36:53.336445+02	f	1	3	3	20
937	{"waste_type": "Food Waste", "quantity_kg": 849, "co2e_emissions": 492.42, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:53.340375+02	2026-01-11 15:36:53.34039+02	f	1	3	3	20
938	{"waste_type": "E-Waste", "quantity_kg": 46, "co2e_emissions": 4.6, "reporting_year": 2020, "disposal_method": "Special Treatment", "reporting_month": "September"}	2026-01-11 15:36:53.344017+02	2026-01-11 15:36:53.34403+02	f	1	3	3	20
939	{"waste_type": "General Waste", "quantity_kg": 2596, "co2e_emissions": 1505.68, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:53.347344+02	2026-01-11 15:36:53.347359+02	f	1	3	3	20
940	{"waste_type": "Paper/Cardboard", "quantity_kg": 851, "co2e_emissions": 17.02, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "October"}	2026-01-11 15:36:53.352538+02	2026-01-11 15:36:53.352553+02	f	1	3	3	20
941	{"waste_type": "Paper/Cardboard", "quantity_kg": 412, "co2e_emissions": 238.96, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:53.356408+02	2026-01-11 15:36:53.356424+02	f	1	3	3	20
942	{"waste_type": "Plastic", "quantity_kg": 197, "co2e_emissions": 3.94, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "October"}	2026-01-11 15:36:53.359955+02	2026-01-11 15:36:53.359968+02	f	1	3	3	20
943	{"waste_type": "Plastic", "quantity_kg": 296, "co2e_emissions": 171.68, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:53.363268+02	2026-01-11 15:36:53.36328+02	f	1	3	3	20
944	{"waste_type": "Food Waste", "quantity_kg": 637, "co2e_emissions": 63.7, "reporting_year": 2020, "disposal_method": "Composted", "reporting_month": "October"}	2026-01-11 15:36:53.366949+02	2026-01-11 15:36:53.36697+02	f	1	3	3	20
945	{"waste_type": "Food Waste", "quantity_kg": 893, "co2e_emissions": 517.94, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:53.371096+02	2026-01-11 15:36:53.371112+02	f	1	3	3	20
946	{"waste_type": "E-Waste", "quantity_kg": 54, "co2e_emissions": 5.4, "reporting_year": 2020, "disposal_method": "Special Treatment", "reporting_month": "October"}	2026-01-11 15:36:53.376844+02	2026-01-11 15:36:53.376858+02	f	1	3	3	20
947	{"waste_type": "General Waste", "quantity_kg": 2690, "co2e_emissions": 1560.2, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:53.380967+02	2026-01-11 15:36:53.380979+02	f	1	3	3	20
948	{"waste_type": "Paper/Cardboard", "quantity_kg": 814, "co2e_emissions": 16.28, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "November"}	2026-01-11 15:36:53.385602+02	2026-01-11 15:36:53.385619+02	f	1	3	3	20
949	{"waste_type": "Paper/Cardboard", "quantity_kg": 362, "co2e_emissions": 209.96, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:53.389104+02	2026-01-11 15:36:53.389116+02	f	1	3	3	20
950	{"waste_type": "Plastic", "quantity_kg": 202, "co2e_emissions": 4.04, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "November"}	2026-01-11 15:36:53.393591+02	2026-01-11 15:36:53.393605+02	f	1	3	3	20
951	{"waste_type": "Plastic", "quantity_kg": 306, "co2e_emissions": 177.48, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:53.397092+02	2026-01-11 15:36:53.397107+02	f	1	3	3	20
952	{"waste_type": "Food Waste", "quantity_kg": 645, "co2e_emissions": 64.5, "reporting_year": 2020, "disposal_method": "Composted", "reporting_month": "November"}	2026-01-11 15:36:53.401922+02	2026-01-11 15:36:53.401939+02	f	1	3	3	20
953	{"waste_type": "Food Waste", "quantity_kg": 987, "co2e_emissions": 572.46, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:53.40656+02	2026-01-11 15:36:53.406574+02	f	1	3	3	20
954	{"waste_type": "E-Waste", "quantity_kg": 54, "co2e_emissions": 5.4, "reporting_year": 2020, "disposal_method": "Special Treatment", "reporting_month": "November"}	2026-01-11 15:36:53.410013+02	2026-01-11 15:36:53.410025+02	f	1	3	3	20
955	{"waste_type": "General Waste", "quantity_kg": 2002, "co2e_emissions": 1161.16, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:53.413285+02	2026-01-11 15:36:53.413298+02	f	1	3	3	20
956	{"waste_type": "Paper/Cardboard", "quantity_kg": 747, "co2e_emissions": 14.94, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "December"}	2026-01-11 15:36:53.417366+02	2026-01-11 15:36:53.417381+02	f	1	3	3	20
957	{"waste_type": "Paper/Cardboard", "quantity_kg": 341, "co2e_emissions": 197.78, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:53.422174+02	2026-01-11 15:36:53.422189+02	f	1	3	3	20
958	{"waste_type": "Plastic", "quantity_kg": 175, "co2e_emissions": 3.5, "reporting_year": 2020, "disposal_method": "Recycled", "reporting_month": "December"}	2026-01-11 15:36:53.425426+02	2026-01-11 15:36:53.425438+02	f	1	3	3	20
959	{"waste_type": "Plastic", "quantity_kg": 244, "co2e_emissions": 141.52, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:53.432712+02	2026-01-11 15:36:53.432727+02	f	1	3	3	20
960	{"waste_type": "Food Waste", "quantity_kg": 513, "co2e_emissions": 51.3, "reporting_year": 2020, "disposal_method": "Composted", "reporting_month": "December"}	2026-01-11 15:36:53.436095+02	2026-01-11 15:36:53.436106+02	f	1	3	3	20
961	{"waste_type": "Food Waste", "quantity_kg": 752, "co2e_emissions": 436.16, "reporting_year": 2020, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:53.439422+02	2026-01-11 15:36:53.439433+02	f	1	3	3	20
962	{"waste_type": "E-Waste", "quantity_kg": 46, "co2e_emissions": 4.6, "reporting_year": 2020, "disposal_method": "Special Treatment", "reporting_month": "December"}	2026-01-11 15:36:53.443864+02	2026-01-11 15:36:53.443876+02	f	1	3	3	20
963	{"waste_type": "General Waste", "quantity_kg": 2356, "co2e_emissions": 1366.48, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:53.447477+02	2026-01-11 15:36:53.447492+02	f	1	3	3	20
964	{"waste_type": "Paper/Cardboard", "quantity_kg": 790, "co2e_emissions": 15.8, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "January"}	2026-01-11 15:36:53.45219+02	2026-01-11 15:36:53.452205+02	f	1	3	3	20
965	{"waste_type": "Paper/Cardboard", "quantity_kg": 353, "co2e_emissions": 204.74, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:53.455829+02	2026-01-11 15:36:53.455844+02	f	1	3	3	20
966	{"waste_type": "Plastic", "quantity_kg": 198, "co2e_emissions": 3.96, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "January"}	2026-01-11 15:36:53.461348+02	2026-01-11 15:36:53.461369+02	f	1	3	3	20
967	{"waste_type": "Plastic", "quantity_kg": 252, "co2e_emissions": 146.16, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:53.465427+02	2026-01-11 15:36:53.465442+02	f	1	3	3	20
968	{"waste_type": "Food Waste", "quantity_kg": 529, "co2e_emissions": 52.9, "reporting_year": 2021, "disposal_method": "Composted", "reporting_month": "January"}	2026-01-11 15:36:53.472051+02	2026-01-11 15:36:53.472066+02	f	1	3	3	20
969	{"waste_type": "Food Waste", "quantity_kg": 758, "co2e_emissions": 439.64, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:53.475822+02	2026-01-11 15:36:53.475836+02	f	1	3	3	20
970	{"waste_type": "E-Waste", "quantity_kg": 42, "co2e_emissions": 4.2, "reporting_year": 2021, "disposal_method": "Special Treatment", "reporting_month": "January"}	2026-01-11 15:36:53.481053+02	2026-01-11 15:36:53.481068+02	f	1	3	3	20
971	{"waste_type": "General Waste", "quantity_kg": 2414, "co2e_emissions": 1400.12, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:53.484411+02	2026-01-11 15:36:53.484422+02	f	1	3	3	20
972	{"waste_type": "Paper/Cardboard", "quantity_kg": 865, "co2e_emissions": 17.3, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "February"}	2026-01-11 15:36:53.487558+02	2026-01-11 15:36:53.48757+02	f	1	3	3	20
973	{"waste_type": "Paper/Cardboard", "quantity_kg": 358, "co2e_emissions": 207.64, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:53.493996+02	2026-01-11 15:36:53.494013+02	f	1	3	3	20
974	{"waste_type": "Plastic", "quantity_kg": 189, "co2e_emissions": 3.78, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "February"}	2026-01-11 15:36:53.497649+02	2026-01-11 15:36:53.49766+02	f	1	3	3	20
975	{"waste_type": "Plastic", "quantity_kg": 284, "co2e_emissions": 164.72, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:53.502079+02	2026-01-11 15:36:53.502091+02	f	1	3	3	20
976	{"waste_type": "Food Waste", "quantity_kg": 633, "co2e_emissions": 63.3, "reporting_year": 2021, "disposal_method": "Composted", "reporting_month": "February"}	2026-01-11 15:36:53.50644+02	2026-01-11 15:36:53.506453+02	f	1	3	3	20
977	{"waste_type": "Food Waste", "quantity_kg": 912, "co2e_emissions": 528.96, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:53.509993+02	2026-01-11 15:36:53.510008+02	f	1	3	3	20
978	{"waste_type": "E-Waste", "quantity_kg": 50, "co2e_emissions": 5.0, "reporting_year": 2021, "disposal_method": "Special Treatment", "reporting_month": "February"}	2026-01-11 15:36:53.513734+02	2026-01-11 15:36:53.513747+02	f	1	3	3	20
979	{"waste_type": "General Waste", "quantity_kg": 2197, "co2e_emissions": 1274.26, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:53.517286+02	2026-01-11 15:36:53.517299+02	f	1	3	3	20
980	{"waste_type": "Paper/Cardboard", "quantity_kg": 782, "co2e_emissions": 15.64, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "March"}	2026-01-11 15:36:53.521876+02	2026-01-11 15:36:53.521888+02	f	1	3	3	20
981	{"waste_type": "Paper/Cardboard", "quantity_kg": 406, "co2e_emissions": 235.48, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:53.526953+02	2026-01-11 15:36:53.526968+02	f	1	3	3	20
982	{"waste_type": "Plastic", "quantity_kg": 192, "co2e_emissions": 3.84, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "March"}	2026-01-11 15:36:53.531956+02	2026-01-11 15:36:53.531971+02	f	1	3	3	20
983	{"waste_type": "Plastic", "quantity_kg": 268, "co2e_emissions": 155.44, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:53.535684+02	2026-01-11 15:36:53.535697+02	f	1	3	3	20
984	{"waste_type": "Food Waste", "quantity_kg": 662, "co2e_emissions": 66.2, "reporting_year": 2021, "disposal_method": "Composted", "reporting_month": "March"}	2026-01-11 15:36:53.539373+02	2026-01-11 15:36:53.53939+02	f	1	3	3	20
985	{"waste_type": "Food Waste", "quantity_kg": 917, "co2e_emissions": 531.86, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:53.543137+02	2026-01-11 15:36:53.543151+02	f	1	3	3	20
986	{"waste_type": "E-Waste", "quantity_kg": 45, "co2e_emissions": 4.5, "reporting_year": 2021, "disposal_method": "Special Treatment", "reporting_month": "March"}	2026-01-11 15:36:53.546471+02	2026-01-11 15:36:53.546482+02	f	1	3	3	20
987	{"waste_type": "General Waste", "quantity_kg": 2197, "co2e_emissions": 1274.26, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:53.549882+02	2026-01-11 15:36:53.549893+02	f	1	3	3	20
988	{"waste_type": "Paper/Cardboard", "quantity_kg": 888, "co2e_emissions": 17.76, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "April"}	2026-01-11 15:36:53.555473+02	2026-01-11 15:36:53.555489+02	f	1	3	3	20
989	{"waste_type": "Paper/Cardboard", "quantity_kg": 373, "co2e_emissions": 216.34, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:53.559233+02	2026-01-11 15:36:53.559247+02	f	1	3	3	20
990	{"waste_type": "Plastic", "quantity_kg": 197, "co2e_emissions": 3.94, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "April"}	2026-01-11 15:36:53.56294+02	2026-01-11 15:36:53.562954+02	f	1	3	3	20
991	{"waste_type": "Plastic", "quantity_kg": 314, "co2e_emissions": 182.12, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:53.566317+02	2026-01-11 15:36:53.566329+02	f	1	3	3	20
992	{"waste_type": "Food Waste", "quantity_kg": 659, "co2e_emissions": 65.9, "reporting_year": 2021, "disposal_method": "Composted", "reporting_month": "April"}	2026-01-11 15:36:53.56976+02	2026-01-11 15:36:53.569776+02	f	1	3	3	20
993	{"waste_type": "Food Waste", "quantity_kg": 855, "co2e_emissions": 495.9, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:53.574317+02	2026-01-11 15:36:53.574333+02	f	1	3	3	20
994	{"waste_type": "E-Waste", "quantity_kg": 48, "co2e_emissions": 4.8, "reporting_year": 2021, "disposal_method": "Special Treatment", "reporting_month": "April"}	2026-01-11 15:36:53.579209+02	2026-01-11 15:36:53.579226+02	f	1	3	3	20
995	{"waste_type": "General Waste", "quantity_kg": 2342, "co2e_emissions": 1358.36, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:53.586225+02	2026-01-11 15:36:53.586242+02	f	1	3	3	20
996	{"waste_type": "Paper/Cardboard", "quantity_kg": 685, "co2e_emissions": 13.7, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "May"}	2026-01-11 15:36:53.595217+02	2026-01-11 15:36:53.595234+02	f	1	3	3	20
997	{"waste_type": "Paper/Cardboard", "quantity_kg": 346, "co2e_emissions": 200.68, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:53.603387+02	2026-01-11 15:36:53.603404+02	f	1	3	3	20
998	{"waste_type": "Plastic", "quantity_kg": 172, "co2e_emissions": 3.44, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "May"}	2026-01-11 15:36:53.61219+02	2026-01-11 15:36:53.612204+02	f	1	3	3	20
999	{"waste_type": "Plastic", "quantity_kg": 277, "co2e_emissions": 160.66, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:53.619097+02	2026-01-11 15:36:53.619113+02	f	1	3	3	20
1000	{"waste_type": "Food Waste", "quantity_kg": 572, "co2e_emissions": 57.2, "reporting_year": 2021, "disposal_method": "Composted", "reporting_month": "May"}	2026-01-11 15:36:53.623945+02	2026-01-11 15:36:53.623961+02	f	1	3	3	20
1001	{"waste_type": "Food Waste", "quantity_kg": 750, "co2e_emissions": 435.0, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:53.63403+02	2026-01-11 15:36:53.634045+02	f	1	3	3	20
1002	{"waste_type": "E-Waste", "quantity_kg": 44, "co2e_emissions": 4.4, "reporting_year": 2021, "disposal_method": "Special Treatment", "reporting_month": "May"}	2026-01-11 15:36:53.637428+02	2026-01-11 15:36:53.637439+02	f	1	3	3	20
1003	{"waste_type": "General Waste", "quantity_kg": 1634, "co2e_emissions": 947.72, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:53.640646+02	2026-01-11 15:36:53.640658+02	f	1	3	3	20
1004	{"waste_type": "Paper/Cardboard", "quantity_kg": 593, "co2e_emissions": 11.86, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "June"}	2026-01-11 15:36:53.645357+02	2026-01-11 15:36:53.64537+02	f	1	3	3	20
1005	{"waste_type": "Paper/Cardboard", "quantity_kg": 245, "co2e_emissions": 142.1, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:53.649441+02	2026-01-11 15:36:53.649457+02	f	1	3	3	20
1006	{"waste_type": "Plastic", "quantity_kg": 160, "co2e_emissions": 3.2, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "June"}	2026-01-11 15:36:53.652816+02	2026-01-11 15:36:53.652829+02	f	1	3	3	20
1007	{"waste_type": "Plastic", "quantity_kg": 202, "co2e_emissions": 117.16, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:53.655931+02	2026-01-11 15:36:53.655942+02	f	1	3	3	20
1008	{"waste_type": "Food Waste", "quantity_kg": 447, "co2e_emissions": 44.7, "reporting_year": 2021, "disposal_method": "Composted", "reporting_month": "June"}	2026-01-11 15:36:53.659104+02	2026-01-11 15:36:53.659118+02	f	1	3	3	20
1009	{"waste_type": "Food Waste", "quantity_kg": 558, "co2e_emissions": 323.64, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:53.665651+02	2026-01-11 15:36:53.665668+02	f	1	3	3	20
1010	{"waste_type": "E-Waste", "quantity_kg": 34, "co2e_emissions": 3.4, "reporting_year": 2021, "disposal_method": "Special Treatment", "reporting_month": "June"}	2026-01-11 15:36:53.669734+02	2026-01-11 15:36:53.669749+02	f	1	3	3	20
1011	{"waste_type": "General Waste", "quantity_kg": 938, "co2e_emissions": 544.04, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:53.673028+02	2026-01-11 15:36:53.673041+02	f	1	3	3	20
1012	{"waste_type": "Paper/Cardboard", "quantity_kg": 334, "co2e_emissions": 6.68, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "July"}	2026-01-11 15:36:53.676577+02	2026-01-11 15:36:53.676589+02	f	1	3	3	20
1013	{"waste_type": "Paper/Cardboard", "quantity_kg": 152, "co2e_emissions": 88.16, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:53.680186+02	2026-01-11 15:36:53.6802+02	f	1	3	3	20
1014	{"waste_type": "Plastic", "quantity_kg": 87, "co2e_emissions": 1.74, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "July"}	2026-01-11 15:36:53.683625+02	2026-01-11 15:36:53.683639+02	f	1	3	3	20
1015	{"waste_type": "Plastic", "quantity_kg": 114, "co2e_emissions": 66.12, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:53.689051+02	2026-01-11 15:36:53.689064+02	f	1	3	3	20
1016	{"waste_type": "Food Waste", "quantity_kg": 240, "co2e_emissions": 24.0, "reporting_year": 2021, "disposal_method": "Composted", "reporting_month": "July"}	2026-01-11 15:36:53.694136+02	2026-01-11 15:36:53.694154+02	f	1	3	3	20
1017	{"waste_type": "Food Waste", "quantity_kg": 368, "co2e_emissions": 213.44, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:53.697933+02	2026-01-11 15:36:53.697948+02	f	1	3	3	20
1018	{"waste_type": "E-Waste", "quantity_kg": 21, "co2e_emissions": 2.1, "reporting_year": 2021, "disposal_method": "Special Treatment", "reporting_month": "July"}	2026-01-11 15:36:53.701621+02	2026-01-11 15:36:53.701643+02	f	1	3	3	20
1019	{"waste_type": "General Waste", "quantity_kg": 767, "co2e_emissions": 444.86, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:53.705435+02	2026-01-11 15:36:53.705449+02	f	1	3	3	20
1020	{"waste_type": "Paper/Cardboard", "quantity_kg": 240, "co2e_emissions": 4.8, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "August"}	2026-01-11 15:36:53.70969+02	2026-01-11 15:36:53.709717+02	f	1	3	3	20
1021	{"waste_type": "Paper/Cardboard", "quantity_kg": 122, "co2e_emissions": 70.76, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:53.714958+02	2026-01-11 15:36:53.714973+02	f	1	3	3	20
1022	{"waste_type": "Plastic", "quantity_kg": 57, "co2e_emissions": 1.14, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "August"}	2026-01-11 15:36:53.718573+02	2026-01-11 15:36:53.718586+02	f	1	3	3	20
1023	{"waste_type": "Plastic", "quantity_kg": 93, "co2e_emissions": 53.94, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:53.722077+02	2026-01-11 15:36:53.72209+02	f	1	3	3	20
1024	{"waste_type": "Food Waste", "quantity_kg": 206, "co2e_emissions": 20.6, "reporting_year": 2021, "disposal_method": "Composted", "reporting_month": "August"}	2026-01-11 15:36:53.726641+02	2026-01-11 15:36:53.726658+02	f	1	3	3	20
1025	{"waste_type": "Food Waste", "quantity_kg": 282, "co2e_emissions": 163.56, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:53.730328+02	2026-01-11 15:36:53.730346+02	f	1	3	3	20
1026	{"waste_type": "E-Waste", "quantity_kg": 14, "co2e_emissions": 1.4, "reporting_year": 2021, "disposal_method": "Special Treatment", "reporting_month": "August"}	2026-01-11 15:36:53.734319+02	2026-01-11 15:36:53.734335+02	f	1	3	3	20
1027	{"waste_type": "General Waste", "quantity_kg": 2475, "co2e_emissions": 1435.5, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:53.737671+02	2026-01-11 15:36:53.737685+02	f	1	3	3	20
1028	{"waste_type": "Paper/Cardboard", "quantity_kg": 815, "co2e_emissions": 16.3, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "September"}	2026-01-11 15:36:53.741336+02	2026-01-11 15:36:53.741362+02	f	1	3	3	20
1029	{"waste_type": "Paper/Cardboard", "quantity_kg": 374, "co2e_emissions": 216.92, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:53.745922+02	2026-01-11 15:36:53.745938+02	f	1	3	3	20
1030	{"waste_type": "Plastic", "quantity_kg": 202, "co2e_emissions": 4.04, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "September"}	2026-01-11 15:36:53.749303+02	2026-01-11 15:36:53.749316+02	f	1	3	3	20
1031	{"waste_type": "Plastic", "quantity_kg": 298, "co2e_emissions": 172.84, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:53.753755+02	2026-01-11 15:36:53.753768+02	f	1	3	3	20
1032	{"waste_type": "Food Waste", "quantity_kg": 569, "co2e_emissions": 56.9, "reporting_year": 2021, "disposal_method": "Composted", "reporting_month": "September"}	2026-01-11 15:36:53.757723+02	2026-01-11 15:36:53.757739+02	f	1	3	3	20
1033	{"waste_type": "Food Waste", "quantity_kg": 827, "co2e_emissions": 479.66, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:53.761394+02	2026-01-11 15:36:53.76141+02	f	1	3	3	20
1034	{"waste_type": "E-Waste", "quantity_kg": 43, "co2e_emissions": 4.3, "reporting_year": 2021, "disposal_method": "Special Treatment", "reporting_month": "September"}	2026-01-11 15:36:53.766493+02	2026-01-11 15:36:53.766507+02	f	1	3	3	20
1035	{"waste_type": "General Waste", "quantity_kg": 2188, "co2e_emissions": 1269.04, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:53.771761+02	2026-01-11 15:36:53.771779+02	f	1	3	3	20
1036	{"waste_type": "Paper/Cardboard", "quantity_kg": 841, "co2e_emissions": 16.82, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "October"}	2026-01-11 15:36:53.775583+02	2026-01-11 15:36:53.775599+02	f	1	3	3	20
1037	{"waste_type": "Paper/Cardboard", "quantity_kg": 360, "co2e_emissions": 208.8, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:53.779092+02	2026-01-11 15:36:53.779105+02	f	1	3	3	20
1038	{"waste_type": "Plastic", "quantity_kg": 225, "co2e_emissions": 4.5, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "October"}	2026-01-11 15:36:53.78241+02	2026-01-11 15:36:53.782425+02	f	1	3	3	20
1039	{"waste_type": "Plastic", "quantity_kg": 315, "co2e_emissions": 182.7, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:53.785902+02	2026-01-11 15:36:53.785916+02	f	1	3	3	20
1040	{"waste_type": "Food Waste", "quantity_kg": 654, "co2e_emissions": 65.4, "reporting_year": 2021, "disposal_method": "Composted", "reporting_month": "October"}	2026-01-11 15:36:53.792113+02	2026-01-11 15:36:53.792128+02	f	1	3	3	20
1041	{"waste_type": "Food Waste", "quantity_kg": 800, "co2e_emissions": 464.0, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:53.795517+02	2026-01-11 15:36:53.795528+02	f	1	3	3	20
1042	{"waste_type": "E-Waste", "quantity_kg": 53, "co2e_emissions": 5.3, "reporting_year": 2021, "disposal_method": "Special Treatment", "reporting_month": "October"}	2026-01-11 15:36:53.798875+02	2026-01-11 15:36:53.798887+02	f	1	3	3	20
1043	{"waste_type": "General Waste", "quantity_kg": 2278, "co2e_emissions": 1321.24, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:53.802552+02	2026-01-11 15:36:53.80258+02	f	1	3	3	20
1044	{"waste_type": "Paper/Cardboard", "quantity_kg": 845, "co2e_emissions": 16.9, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "November"}	2026-01-11 15:36:53.806976+02	2026-01-11 15:36:53.806996+02	f	1	3	3	20
1045	{"waste_type": "Paper/Cardboard", "quantity_kg": 355, "co2e_emissions": 205.9, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:53.812161+02	2026-01-11 15:36:53.812179+02	f	1	3	3	20
1046	{"waste_type": "Plastic", "quantity_kg": 211, "co2e_emissions": 4.22, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "November"}	2026-01-11 15:36:53.817971+02	2026-01-11 15:36:53.817996+02	f	1	3	3	20
1047	{"waste_type": "Plastic", "quantity_kg": 292, "co2e_emissions": 169.36, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:53.822171+02	2026-01-11 15:36:53.822187+02	f	1	3	3	20
1048	{"waste_type": "Food Waste", "quantity_kg": 594, "co2e_emissions": 59.4, "reporting_year": 2021, "disposal_method": "Composted", "reporting_month": "November"}	2026-01-11 15:36:53.827087+02	2026-01-11 15:36:53.827101+02	f	1	3	3	20
1049	{"waste_type": "Food Waste", "quantity_kg": 792, "co2e_emissions": 459.36, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:53.831846+02	2026-01-11 15:36:53.83186+02	f	1	3	3	20
1050	{"waste_type": "E-Waste", "quantity_kg": 53, "co2e_emissions": 5.3, "reporting_year": 2021, "disposal_method": "Special Treatment", "reporting_month": "November"}	2026-01-11 15:36:53.835494+02	2026-01-11 15:36:53.835537+02	f	1	3	3	20
1051	{"waste_type": "General Waste", "quantity_kg": 1906, "co2e_emissions": 1105.48, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:53.839242+02	2026-01-11 15:36:53.839256+02	f	1	3	3	20
1052	{"waste_type": "Paper/Cardboard", "quantity_kg": 669, "co2e_emissions": 13.38, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "December"}	2026-01-11 15:36:53.842595+02	2026-01-11 15:36:53.842608+02	f	1	3	3	20
1053	{"waste_type": "Paper/Cardboard", "quantity_kg": 333, "co2e_emissions": 193.14, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:53.845888+02	2026-01-11 15:36:53.845903+02	f	1	3	3	20
1054	{"waste_type": "Plastic", "quantity_kg": 171, "co2e_emissions": 3.42, "reporting_year": 2021, "disposal_method": "Recycled", "reporting_month": "December"}	2026-01-11 15:36:53.850841+02	2026-01-11 15:36:53.850857+02	f	1	3	3	20
1055	{"waste_type": "Plastic", "quantity_kg": 263, "co2e_emissions": 152.54, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:53.854514+02	2026-01-11 15:36:53.85453+02	f	1	3	3	20
1056	{"waste_type": "Food Waste", "quantity_kg": 486, "co2e_emissions": 48.6, "reporting_year": 2021, "disposal_method": "Composted", "reporting_month": "December"}	2026-01-11 15:36:53.858089+02	2026-01-11 15:36:53.858101+02	f	1	3	3	20
1057	{"waste_type": "Food Waste", "quantity_kg": 799, "co2e_emissions": 463.42, "reporting_year": 2021, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:53.861329+02	2026-01-11 15:36:53.861341+02	f	1	3	3	20
1058	{"waste_type": "E-Waste", "quantity_kg": 46, "co2e_emissions": 4.6, "reporting_year": 2021, "disposal_method": "Special Treatment", "reporting_month": "December"}	2026-01-11 15:36:53.864968+02	2026-01-11 15:36:53.86499+02	f	1	3	3	20
1059	{"waste_type": "General Waste", "quantity_kg": 2100, "co2e_emissions": 1218.0, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:53.868698+02	2026-01-11 15:36:53.868713+02	f	1	3	3	20
1060	{"waste_type": "Paper/Cardboard", "quantity_kg": 795, "co2e_emissions": 15.9, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "January"}	2026-01-11 15:36:53.873317+02	2026-01-11 15:36:53.87333+02	f	1	3	3	20
1061	{"waste_type": "Paper/Cardboard", "quantity_kg": 366, "co2e_emissions": 212.28, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:53.877474+02	2026-01-11 15:36:53.877488+02	f	1	3	3	20
1062	{"waste_type": "Plastic", "quantity_kg": 196, "co2e_emissions": 3.92, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "January"}	2026-01-11 15:36:53.881244+02	2026-01-11 15:36:53.881266+02	f	1	3	3	20
1063	{"waste_type": "Plastic", "quantity_kg": 232, "co2e_emissions": 134.56, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:53.88487+02	2026-01-11 15:36:53.884885+02	f	1	3	3	20
1064	{"waste_type": "Food Waste", "quantity_kg": 539, "co2e_emissions": 53.9, "reporting_year": 2022, "disposal_method": "Composted", "reporting_month": "January"}	2026-01-11 15:36:53.888118+02	2026-01-11 15:36:53.88813+02	f	1	3	3	20
1065	{"waste_type": "Food Waste", "quantity_kg": 741, "co2e_emissions": 429.78, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:53.892586+02	2026-01-11 15:36:53.892599+02	f	1	3	3	20
1066	{"waste_type": "E-Waste", "quantity_kg": 46, "co2e_emissions": 4.6, "reporting_year": 2022, "disposal_method": "Special Treatment", "reporting_month": "January"}	2026-01-11 15:36:53.896302+02	2026-01-11 15:36:53.89632+02	f	1	3	3	20
1067	{"waste_type": "General Waste", "quantity_kg": 2377, "co2e_emissions": 1378.66, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:53.900094+02	2026-01-11 15:36:53.900108+02	f	1	3	3	20
1068	{"waste_type": "Paper/Cardboard", "quantity_kg": 850, "co2e_emissions": 17.0, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "February"}	2026-01-11 15:36:53.903348+02	2026-01-11 15:36:53.90336+02	f	1	3	3	20
1069	{"waste_type": "Paper/Cardboard", "quantity_kg": 394, "co2e_emissions": 228.52, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:53.908267+02	2026-01-11 15:36:53.908278+02	f	1	3	3	20
1070	{"waste_type": "Plastic", "quantity_kg": 228, "co2e_emissions": 4.56, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "February"}	2026-01-11 15:36:53.911887+02	2026-01-11 15:36:53.911905+02	f	1	3	3	20
1071	{"waste_type": "Plastic", "quantity_kg": 284, "co2e_emissions": 164.72, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:53.915643+02	2026-01-11 15:36:53.915658+02	f	1	3	3	20
1072	{"waste_type": "Food Waste", "quantity_kg": 598, "co2e_emissions": 59.8, "reporting_year": 2022, "disposal_method": "Composted", "reporting_month": "February"}	2026-01-11 15:36:53.919001+02	2026-01-11 15:36:53.919013+02	f	1	3	3	20
1073	{"waste_type": "Food Waste", "quantity_kg": 862, "co2e_emissions": 499.96, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:53.922233+02	2026-01-11 15:36:53.922246+02	f	1	3	3	20
1074	{"waste_type": "E-Waste", "quantity_kg": 52, "co2e_emissions": 5.2, "reporting_year": 2022, "disposal_method": "Special Treatment", "reporting_month": "February"}	2026-01-11 15:36:53.926873+02	2026-01-11 15:36:53.926891+02	f	1	3	3	20
1075	{"waste_type": "General Waste", "quantity_kg": 2376, "co2e_emissions": 1378.08, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:53.9311+02	2026-01-11 15:36:53.931116+02	f	1	3	3	20
1076	{"waste_type": "Paper/Cardboard", "quantity_kg": 808, "co2e_emissions": 16.16, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "March"}	2026-01-11 15:36:53.934564+02	2026-01-11 15:36:53.934581+02	f	1	3	3	20
1077	{"waste_type": "Paper/Cardboard", "quantity_kg": 379, "co2e_emissions": 219.82, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:53.93789+02	2026-01-11 15:36:53.937903+02	f	1	3	3	20
1078	{"waste_type": "Plastic", "quantity_kg": 213, "co2e_emissions": 4.26, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "March"}	2026-01-11 15:36:53.941163+02	2026-01-11 15:36:53.941176+02	f	1	3	3	20
1079	{"waste_type": "Plastic", "quantity_kg": 258, "co2e_emissions": 149.64, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:53.94566+02	2026-01-11 15:36:53.945676+02	f	1	3	3	20
1080	{"waste_type": "Food Waste", "quantity_kg": 711, "co2e_emissions": 71.1, "reporting_year": 2022, "disposal_method": "Composted", "reporting_month": "March"}	2026-01-11 15:36:53.949161+02	2026-01-11 15:36:53.949174+02	f	1	3	3	20
1081	{"waste_type": "Food Waste", "quantity_kg": 821, "co2e_emissions": 476.18, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:53.953662+02	2026-01-11 15:36:53.953676+02	f	1	3	3	20
1082	{"waste_type": "E-Waste", "quantity_kg": 45, "co2e_emissions": 4.5, "reporting_year": 2022, "disposal_method": "Special Treatment", "reporting_month": "March"}	2026-01-11 15:36:53.957088+02	2026-01-11 15:36:53.957102+02	f	1	3	3	20
1083	{"waste_type": "General Waste", "quantity_kg": 2513, "co2e_emissions": 1457.54, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:53.960755+02	2026-01-11 15:36:53.96077+02	f	1	3	3	20
1084	{"waste_type": "Paper/Cardboard", "quantity_kg": 928, "co2e_emissions": 18.56, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "April"}	2026-01-11 15:36:53.964011+02	2026-01-11 15:36:53.964023+02	f	1	3	3	20
1085	{"waste_type": "Paper/Cardboard", "quantity_kg": 397, "co2e_emissions": 230.26, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:53.967158+02	2026-01-11 15:36:53.967178+02	f	1	3	3	20
1086	{"waste_type": "Plastic", "quantity_kg": 225, "co2e_emissions": 4.5, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "April"}	2026-01-11 15:36:53.971794+02	2026-01-11 15:36:53.971811+02	f	1	3	3	20
1087	{"waste_type": "Plastic", "quantity_kg": 294, "co2e_emissions": 170.52, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:53.97572+02	2026-01-11 15:36:53.97574+02	f	1	3	3	20
1088	{"waste_type": "Food Waste", "quantity_kg": 613, "co2e_emissions": 61.3, "reporting_year": 2022, "disposal_method": "Composted", "reporting_month": "April"}	2026-01-11 15:36:53.979242+02	2026-01-11 15:36:53.979257+02	f	1	3	3	20
1089	{"waste_type": "Food Waste", "quantity_kg": 827, "co2e_emissions": 479.66, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:53.982624+02	2026-01-11 15:36:53.982639+02	f	1	3	3	20
1090	{"waste_type": "E-Waste", "quantity_kg": 54, "co2e_emissions": 5.4, "reporting_year": 2022, "disposal_method": "Special Treatment", "reporting_month": "April"}	2026-01-11 15:36:53.985917+02	2026-01-11 15:36:53.985931+02	f	1	3	3	20
1091	{"waste_type": "General Waste", "quantity_kg": 2192, "co2e_emissions": 1271.36, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:53.992199+02	2026-01-11 15:36:53.992215+02	f	1	3	3	20
1092	{"waste_type": "Paper/Cardboard", "quantity_kg": 865, "co2e_emissions": 17.3, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "May"}	2026-01-11 15:36:53.996266+02	2026-01-11 15:36:53.996281+02	f	1	3	3	20
1093	{"waste_type": "Paper/Cardboard", "quantity_kg": 341, "co2e_emissions": 197.78, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:53.999917+02	2026-01-11 15:36:53.999934+02	f	1	3	3	20
1094	{"waste_type": "Plastic", "quantity_kg": 216, "co2e_emissions": 4.32, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "May"}	2026-01-11 15:36:54.003895+02	2026-01-11 15:36:54.003918+02	f	1	3	3	20
1095	{"waste_type": "Plastic", "quantity_kg": 271, "co2e_emissions": 157.18, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:54.009551+02	2026-01-11 15:36:54.009567+02	f	1	3	3	20
1096	{"waste_type": "Food Waste", "quantity_kg": 642, "co2e_emissions": 64.2, "reporting_year": 2022, "disposal_method": "Composted", "reporting_month": "May"}	2026-01-11 15:36:54.013151+02	2026-01-11 15:36:54.013166+02	f	1	3	3	20
1097	{"waste_type": "Food Waste", "quantity_kg": 699, "co2e_emissions": 405.42, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:54.021318+02	2026-01-11 15:36:54.021334+02	f	1	3	3	20
1098	{"waste_type": "E-Waste", "quantity_kg": 48, "co2e_emissions": 4.8, "reporting_year": 2022, "disposal_method": "Special Treatment", "reporting_month": "May"}	2026-01-11 15:36:54.026872+02	2026-01-11 15:36:54.026887+02	f	1	3	3	20
1099	{"waste_type": "General Waste", "quantity_kg": 1605, "co2e_emissions": 930.9, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:54.030457+02	2026-01-11 15:36:54.030472+02	f	1	3	3	20
1100	{"waste_type": "Paper/Cardboard", "quantity_kg": 631, "co2e_emissions": 12.62, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "June"}	2026-01-11 15:36:54.034031+02	2026-01-11 15:36:54.034046+02	f	1	3	3	20
1101	{"waste_type": "Paper/Cardboard", "quantity_kg": 273, "co2e_emissions": 158.34, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:54.038007+02	2026-01-11 15:36:54.038022+02	f	1	3	3	20
1102	{"waste_type": "Plastic", "quantity_kg": 141, "co2e_emissions": 2.82, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "June"}	2026-01-11 15:36:54.042047+02	2026-01-11 15:36:54.042062+02	f	1	3	3	20
1103	{"waste_type": "Plastic", "quantity_kg": 186, "co2e_emissions": 107.88, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:54.046775+02	2026-01-11 15:36:54.046789+02	f	1	3	3	20
1104	{"waste_type": "Food Waste", "quantity_kg": 468, "co2e_emissions": 46.8, "reporting_year": 2022, "disposal_method": "Composted", "reporting_month": "June"}	2026-01-11 15:36:54.050193+02	2026-01-11 15:36:54.050208+02	f	1	3	3	20
1105	{"waste_type": "Food Waste", "quantity_kg": 579, "co2e_emissions": 335.82, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:54.054325+02	2026-01-11 15:36:54.054343+02	f	1	3	3	20
1106	{"waste_type": "E-Waste", "quantity_kg": 37, "co2e_emissions": 3.7, "reporting_year": 2022, "disposal_method": "Special Treatment", "reporting_month": "June"}	2026-01-11 15:36:54.058247+02	2026-01-11 15:36:54.058262+02	f	1	3	3	20
1107	{"waste_type": "General Waste", "quantity_kg": 905, "co2e_emissions": 524.9, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:54.063793+02	2026-01-11 15:36:54.063807+02	f	1	3	3	20
1108	{"waste_type": "Paper/Cardboard", "quantity_kg": 346, "co2e_emissions": 6.92, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "July"}	2026-01-11 15:36:54.067558+02	2026-01-11 15:36:54.067582+02	f	1	3	3	20
1109	{"waste_type": "Paper/Cardboard", "quantity_kg": 164, "co2e_emissions": 95.12, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:54.07124+02	2026-01-11 15:36:54.071255+02	f	1	3	3	20
1110	{"waste_type": "Plastic", "quantity_kg": 81, "co2e_emissions": 1.62, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "July"}	2026-01-11 15:36:54.074719+02	2026-01-11 15:36:54.074732+02	f	1	3	3	20
1111	{"waste_type": "Plastic", "quantity_kg": 116, "co2e_emissions": 67.28, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:54.07784+02	2026-01-11 15:36:54.077852+02	f	1	3	3	20
1112	{"waste_type": "Food Waste", "quantity_kg": 276, "co2e_emissions": 27.6, "reporting_year": 2022, "disposal_method": "Composted", "reporting_month": "July"}	2026-01-11 15:36:54.082976+02	2026-01-11 15:36:54.082991+02	f	1	3	3	20
1113	{"waste_type": "Food Waste", "quantity_kg": 336, "co2e_emissions": 194.88, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:54.087968+02	2026-01-11 15:36:54.087985+02	f	1	3	3	20
1114	{"waste_type": "E-Waste", "quantity_kg": 21, "co2e_emissions": 2.1, "reporting_year": 2022, "disposal_method": "Special Treatment", "reporting_month": "July"}	2026-01-11 15:36:54.091702+02	2026-01-11 15:36:54.091717+02	f	1	3	3	20
1115	{"waste_type": "General Waste", "quantity_kg": 746, "co2e_emissions": 432.68, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:54.095425+02	2026-01-11 15:36:54.095438+02	f	1	3	3	20
1116	{"waste_type": "Paper/Cardboard", "quantity_kg": 253, "co2e_emissions": 5.06, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "August"}	2026-01-11 15:36:54.100554+02	2026-01-11 15:36:54.100569+02	f	1	3	3	20
1117	{"waste_type": "Paper/Cardboard", "quantity_kg": 121, "co2e_emissions": 70.18, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:54.104322+02	2026-01-11 15:36:54.104335+02	f	1	3	3	20
1118	{"waste_type": "Plastic", "quantity_kg": 64, "co2e_emissions": 1.28, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "August"}	2026-01-11 15:36:54.10771+02	2026-01-11 15:36:54.107724+02	f	1	3	3	20
1119	{"waste_type": "Plastic", "quantity_kg": 81, "co2e_emissions": 46.98, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:54.111088+02	2026-01-11 15:36:54.1111+02	f	1	3	3	20
1120	{"waste_type": "Food Waste", "quantity_kg": 215, "co2e_emissions": 21.5, "reporting_year": 2022, "disposal_method": "Composted", "reporting_month": "August"}	2026-01-11 15:36:54.114839+02	2026-01-11 15:36:54.114854+02	f	1	3	3	20
1121	{"waste_type": "Food Waste", "quantity_kg": 233, "co2e_emissions": 135.14, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:54.119021+02	2026-01-11 15:36:54.119035+02	f	1	3	3	20
1122	{"waste_type": "E-Waste", "quantity_kg": 13, "co2e_emissions": 1.3, "reporting_year": 2022, "disposal_method": "Special Treatment", "reporting_month": "August"}	2026-01-11 15:36:54.122429+02	2026-01-11 15:36:54.122441+02	f	1	3	3	20
1123	{"waste_type": "General Waste", "quantity_kg": 2195, "co2e_emissions": 1273.1, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:54.125809+02	2026-01-11 15:36:54.125822+02	f	1	3	3	20
1124	{"waste_type": "Paper/Cardboard", "quantity_kg": 762, "co2e_emissions": 15.24, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "September"}	2026-01-11 15:36:54.129708+02	2026-01-11 15:36:54.129728+02	f	1	3	3	20
1125	{"waste_type": "Paper/Cardboard", "quantity_kg": 364, "co2e_emissions": 211.12, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:54.133661+02	2026-01-11 15:36:54.133678+02	f	1	3	3	20
1126	{"waste_type": "Plastic", "quantity_kg": 208, "co2e_emissions": 4.16, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "September"}	2026-01-11 15:36:54.13887+02	2026-01-11 15:36:54.138885+02	f	1	3	3	20
1127	{"waste_type": "Plastic", "quantity_kg": 242, "co2e_emissions": 140.36, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:54.143233+02	2026-01-11 15:36:54.143248+02	f	1	3	3	20
1128	{"waste_type": "Food Waste", "quantity_kg": 671, "co2e_emissions": 67.1, "reporting_year": 2022, "disposal_method": "Composted", "reporting_month": "September"}	2026-01-11 15:36:54.147439+02	2026-01-11 15:36:54.147455+02	f	1	3	3	20
1129	{"waste_type": "Food Waste", "quantity_kg": 757, "co2e_emissions": 439.06, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:54.150922+02	2026-01-11 15:36:54.150934+02	f	1	3	3	20
1130	{"waste_type": "E-Waste", "quantity_kg": 42, "co2e_emissions": 4.2, "reporting_year": 2022, "disposal_method": "Special Treatment", "reporting_month": "September"}	2026-01-11 15:36:54.154243+02	2026-01-11 15:36:54.154255+02	f	1	3	3	20
1131	{"waste_type": "General Waste", "quantity_kg": 2456, "co2e_emissions": 1424.48, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:54.157485+02	2026-01-11 15:36:54.157498+02	f	1	3	3	20
1132	{"waste_type": "Paper/Cardboard", "quantity_kg": 793, "co2e_emissions": 15.86, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "October"}	2026-01-11 15:36:54.161315+02	2026-01-11 15:36:54.161331+02	f	1	3	3	20
1133	{"waste_type": "Paper/Cardboard", "quantity_kg": 403, "co2e_emissions": 233.74, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:54.164741+02	2026-01-11 15:36:54.164755+02	f	1	3	3	20
1134	{"waste_type": "Plastic", "quantity_kg": 214, "co2e_emissions": 4.28, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "October"}	2026-01-11 15:36:54.168264+02	2026-01-11 15:36:54.168278+02	f	1	3	3	20
1135	{"waste_type": "Plastic", "quantity_kg": 306, "co2e_emissions": 177.48, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:54.17165+02	2026-01-11 15:36:54.171664+02	f	1	3	3	20
1136	{"waste_type": "Food Waste", "quantity_kg": 698, "co2e_emissions": 69.8, "reporting_year": 2022, "disposal_method": "Composted", "reporting_month": "October"}	2026-01-11 15:36:54.175155+02	2026-01-11 15:36:54.175176+02	f	1	3	3	20
1137	{"waste_type": "Food Waste", "quantity_kg": 771, "co2e_emissions": 447.18, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:54.180658+02	2026-01-11 15:36:54.180674+02	f	1	3	3	20
1138	{"waste_type": "E-Waste", "quantity_kg": 48, "co2e_emissions": 4.8, "reporting_year": 2022, "disposal_method": "Special Treatment", "reporting_month": "October"}	2026-01-11 15:36:54.184272+02	2026-01-11 15:36:54.184285+02	f	1	3	3	20
1139	{"waste_type": "General Waste", "quantity_kg": 2453, "co2e_emissions": 1422.74, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:54.187801+02	2026-01-11 15:36:54.187814+02	f	1	3	3	20
1140	{"waste_type": "Paper/Cardboard", "quantity_kg": 811, "co2e_emissions": 16.22, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "November"}	2026-01-11 15:36:54.194365+02	2026-01-11 15:36:54.19438+02	f	1	3	3	20
1141	{"waste_type": "Paper/Cardboard", "quantity_kg": 342, "co2e_emissions": 198.36, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:54.198243+02	2026-01-11 15:36:54.198257+02	f	1	3	3	20
1142	{"waste_type": "Plastic", "quantity_kg": 204, "co2e_emissions": 4.08, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "November"}	2026-01-11 15:36:54.201728+02	2026-01-11 15:36:54.201742+02	f	1	3	3	20
1143	{"waste_type": "Plastic", "quantity_kg": 299, "co2e_emissions": 173.42, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:54.205612+02	2026-01-11 15:36:54.205638+02	f	1	3	3	20
1144	{"waste_type": "Food Waste", "quantity_kg": 620, "co2e_emissions": 62.0, "reporting_year": 2022, "disposal_method": "Composted", "reporting_month": "November"}	2026-01-11 15:36:54.209612+02	2026-01-11 15:36:54.209628+02	f	1	3	3	20
1145	{"waste_type": "Food Waste", "quantity_kg": 828, "co2e_emissions": 480.24, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:54.216028+02	2026-01-11 15:36:54.216043+02	f	1	3	3	20
1146	{"waste_type": "E-Waste", "quantity_kg": 50, "co2e_emissions": 5.0, "reporting_year": 2022, "disposal_method": "Special Treatment", "reporting_month": "November"}	2026-01-11 15:36:54.219597+02	2026-01-11 15:36:54.219611+02	f	1	3	3	20
1147	{"waste_type": "General Waste", "quantity_kg": 2091, "co2e_emissions": 1212.78, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:54.223618+02	2026-01-11 15:36:54.223634+02	f	1	3	3	20
1148	{"waste_type": "Paper/Cardboard", "quantity_kg": 696, "co2e_emissions": 13.92, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "December"}	2026-01-11 15:36:54.227656+02	2026-01-11 15:36:54.227671+02	f	1	3	3	20
1149	{"waste_type": "Paper/Cardboard", "quantity_kg": 312, "co2e_emissions": 180.96, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:54.230963+02	2026-01-11 15:36:54.230977+02	f	1	3	3	20
1150	{"waste_type": "Plastic", "quantity_kg": 190, "co2e_emissions": 3.8, "reporting_year": 2022, "disposal_method": "Recycled", "reporting_month": "December"}	2026-01-11 15:36:54.235595+02	2026-01-11 15:36:54.235628+02	f	1	3	3	20
1151	{"waste_type": "Plastic", "quantity_kg": 233, "co2e_emissions": 135.14, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:54.240132+02	2026-01-11 15:36:54.240149+02	f	1	3	3	20
1152	{"waste_type": "Food Waste", "quantity_kg": 557, "co2e_emissions": 55.7, "reporting_year": 2022, "disposal_method": "Composted", "reporting_month": "December"}	2026-01-11 15:36:54.24465+02	2026-01-11 15:36:54.244675+02	f	1	3	3	20
1153	{"waste_type": "Food Waste", "quantity_kg": 759, "co2e_emissions": 440.22, "reporting_year": 2022, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:54.248808+02	2026-01-11 15:36:54.248834+02	f	1	3	3	20
1154	{"waste_type": "E-Waste", "quantity_kg": 46, "co2e_emissions": 4.6, "reporting_year": 2022, "disposal_method": "Special Treatment", "reporting_month": "December"}	2026-01-11 15:36:54.253197+02	2026-01-11 15:36:54.253224+02	f	1	3	3	20
1155	{"waste_type": "General Waste", "quantity_kg": 1930, "co2e_emissions": 1119.4, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:54.258157+02	2026-01-11 15:36:54.258174+02	f	1	3	3	20
1156	{"waste_type": "Paper/Cardboard", "quantity_kg": 871, "co2e_emissions": 17.42, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "January"}	2026-01-11 15:36:54.26192+02	2026-01-11 15:36:54.261937+02	f	1	3	3	20
1157	{"waste_type": "Paper/Cardboard", "quantity_kg": 320, "co2e_emissions": 185.6, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:54.266929+02	2026-01-11 15:36:54.266946+02	f	1	3	3	20
1158	{"waste_type": "Plastic", "quantity_kg": 220, "co2e_emissions": 4.4, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "January"}	2026-01-11 15:36:54.270962+02	2026-01-11 15:36:54.270978+02	f	1	3	3	20
1159	{"waste_type": "Plastic", "quantity_kg": 251, "co2e_emissions": 145.58, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:54.275368+02	2026-01-11 15:36:54.275382+02	f	1	3	3	20
1160	{"waste_type": "Food Waste", "quantity_kg": 633, "co2e_emissions": 63.3, "reporting_year": 2023, "disposal_method": "Composted", "reporting_month": "January"}	2026-01-11 15:36:54.279607+02	2026-01-11 15:36:54.279622+02	f	1	3	3	20
1161	{"waste_type": "Food Waste", "quantity_kg": 746, "co2e_emissions": 432.68, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:54.284004+02	2026-01-11 15:36:54.284033+02	f	1	3	3	20
1162	{"waste_type": "E-Waste", "quantity_kg": 46, "co2e_emissions": 4.6, "reporting_year": 2023, "disposal_method": "Special Treatment", "reporting_month": "January"}	2026-01-11 15:36:54.289183+02	2026-01-11 15:36:54.289211+02	f	1	3	3	20
1163	{"waste_type": "General Waste", "quantity_kg": 2314, "co2e_emissions": 1342.12, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:54.293254+02	2026-01-11 15:36:54.293267+02	f	1	3	3	20
1164	{"waste_type": "Paper/Cardboard", "quantity_kg": 929, "co2e_emissions": 18.58, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "February"}	2026-01-11 15:36:54.296946+02	2026-01-11 15:36:54.29696+02	f	1	3	3	20
1165	{"waste_type": "Paper/Cardboard", "quantity_kg": 398, "co2e_emissions": 230.84, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:54.302717+02	2026-01-11 15:36:54.302732+02	f	1	3	3	20
1166	{"waste_type": "Plastic", "quantity_kg": 217, "co2e_emissions": 4.34, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "February"}	2026-01-11 15:36:54.306626+02	2026-01-11 15:36:54.306647+02	f	1	3	3	20
1167	{"waste_type": "Plastic", "quantity_kg": 273, "co2e_emissions": 158.34, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:54.311085+02	2026-01-11 15:36:54.3111+02	f	1	3	3	20
1168	{"waste_type": "Food Waste", "quantity_kg": 727, "co2e_emissions": 72.7, "reporting_year": 2023, "disposal_method": "Composted", "reporting_month": "February"}	2026-01-11 15:36:54.314832+02	2026-01-11 15:36:54.314848+02	f	1	3	3	20
1169	{"waste_type": "Food Waste", "quantity_kg": 892, "co2e_emissions": 517.36, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:54.318731+02	2026-01-11 15:36:54.318747+02	f	1	3	3	20
1170	{"waste_type": "E-Waste", "quantity_kg": 54, "co2e_emissions": 5.4, "reporting_year": 2023, "disposal_method": "Special Treatment", "reporting_month": "February"}	2026-01-11 15:36:54.323102+02	2026-01-11 15:36:54.323117+02	f	1	3	3	20
1171	{"waste_type": "General Waste", "quantity_kg": 2495, "co2e_emissions": 1447.1, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:54.326571+02	2026-01-11 15:36:54.326585+02	f	1	3	3	20
1172	{"waste_type": "Paper/Cardboard", "quantity_kg": 948, "co2e_emissions": 18.96, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "March"}	2026-01-11 15:36:54.333027+02	2026-01-11 15:36:54.333044+02	f	1	3	3	20
1173	{"waste_type": "Paper/Cardboard", "quantity_kg": 340, "co2e_emissions": 197.2, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:54.336657+02	2026-01-11 15:36:54.336671+02	f	1	3	3	20
1174	{"waste_type": "Plastic", "quantity_kg": 230, "co2e_emissions": 4.6, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "March"}	2026-01-11 15:36:54.340099+02	2026-01-11 15:36:54.340113+02	f	1	3	3	20
1175	{"waste_type": "Plastic", "quantity_kg": 293, "co2e_emissions": 169.94, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:54.34358+02	2026-01-11 15:36:54.343594+02	f	1	3	3	20
1176	{"waste_type": "Food Waste", "quantity_kg": 694, "co2e_emissions": 69.4, "reporting_year": 2023, "disposal_method": "Composted", "reporting_month": "March"}	2026-01-11 15:36:54.347807+02	2026-01-11 15:36:54.347825+02	f	1	3	3	20
1177	{"waste_type": "Food Waste", "quantity_kg": 814, "co2e_emissions": 472.12, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:54.353826+02	2026-01-11 15:36:54.35384+02	f	1	3	3	20
1178	{"waste_type": "E-Waste", "quantity_kg": 49, "co2e_emissions": 4.9, "reporting_year": 2023, "disposal_method": "Special Treatment", "reporting_month": "March"}	2026-01-11 15:36:54.357705+02	2026-01-11 15:36:54.357723+02	f	1	3	3	20
1179	{"waste_type": "General Waste", "quantity_kg": 2402, "co2e_emissions": 1393.16, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:54.361785+02	2026-01-11 15:36:54.361816+02	f	1	3	3	20
1180	{"waste_type": "Paper/Cardboard", "quantity_kg": 887, "co2e_emissions": 17.74, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "April"}	2026-01-11 15:36:54.366258+02	2026-01-11 15:36:54.366283+02	f	1	3	3	20
1181	{"waste_type": "Paper/Cardboard", "quantity_kg": 350, "co2e_emissions": 203.0, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:54.371526+02	2026-01-11 15:36:54.371543+02	f	1	3	3	20
1182	{"waste_type": "Plastic", "quantity_kg": 222, "co2e_emissions": 4.44, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "April"}	2026-01-11 15:36:54.376562+02	2026-01-11 15:36:54.376587+02	f	1	3	3	20
1183	{"waste_type": "Plastic", "quantity_kg": 268, "co2e_emissions": 155.44, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:54.380617+02	2026-01-11 15:36:54.380633+02	f	1	3	3	20
1184	{"waste_type": "Food Waste", "quantity_kg": 732, "co2e_emissions": 73.2, "reporting_year": 2023, "disposal_method": "Composted", "reporting_month": "April"}	2026-01-11 15:36:54.384239+02	2026-01-11 15:36:54.384253+02	f	1	3	3	20
1185	{"waste_type": "Food Waste", "quantity_kg": 885, "co2e_emissions": 513.3, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:54.387748+02	2026-01-11 15:36:54.387761+02	f	1	3	3	20
1186	{"waste_type": "E-Waste", "quantity_kg": 47, "co2e_emissions": 4.7, "reporting_year": 2023, "disposal_method": "Special Treatment", "reporting_month": "April"}	2026-01-11 15:36:54.391495+02	2026-01-11 15:36:54.391507+02	f	1	3	3	20
1187	{"waste_type": "General Waste", "quantity_kg": 1861, "co2e_emissions": 1079.38, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:54.395588+02	2026-01-11 15:36:54.395606+02	f	1	3	3	20
1188	{"waste_type": "Paper/Cardboard", "quantity_kg": 871, "co2e_emissions": 17.42, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "May"}	2026-01-11 15:36:54.399205+02	2026-01-11 15:36:54.399219+02	f	1	3	3	20
1189	{"waste_type": "Paper/Cardboard", "quantity_kg": 351, "co2e_emissions": 203.58, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:54.402963+02	2026-01-11 15:36:54.402979+02	f	1	3	3	20
1190	{"waste_type": "Plastic", "quantity_kg": 193, "co2e_emissions": 3.86, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "May"}	2026-01-11 15:36:54.40862+02	2026-01-11 15:36:54.408638+02	f	1	3	3	20
1191	{"waste_type": "Plastic", "quantity_kg": 240, "co2e_emissions": 139.2, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:54.413903+02	2026-01-11 15:36:54.413922+02	f	1	3	3	20
1192	{"waste_type": "Food Waste", "quantity_kg": 639, "co2e_emissions": 63.9, "reporting_year": 2023, "disposal_method": "Composted", "reporting_month": "May"}	2026-01-11 15:36:54.417695+02	2026-01-11 15:36:54.41771+02	f	1	3	3	20
1193	{"waste_type": "Food Waste", "quantity_kg": 742, "co2e_emissions": 430.36, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:54.421673+02	2026-01-11 15:36:54.42169+02	f	1	3	3	20
1194	{"waste_type": "E-Waste", "quantity_kg": 49, "co2e_emissions": 4.9, "reporting_year": 2023, "disposal_method": "Special Treatment", "reporting_month": "May"}	2026-01-11 15:36:54.425364+02	2026-01-11 15:36:54.425386+02	f	1	3	3	20
1195	{"waste_type": "General Waste", "quantity_kg": 1468, "co2e_emissions": 851.44, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:54.428975+02	2026-01-11 15:36:54.42899+02	f	1	3	3	20
1196	{"waste_type": "Paper/Cardboard", "quantity_kg": 603, "co2e_emissions": 12.06, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "June"}	2026-01-11 15:36:54.432456+02	2026-01-11 15:36:54.43247+02	f	1	3	3	20
1197	{"waste_type": "Paper/Cardboard", "quantity_kg": 270, "co2e_emissions": 156.6, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:54.436256+02	2026-01-11 15:36:54.436269+02	f	1	3	3	20
1198	{"waste_type": "Plastic", "quantity_kg": 150, "co2e_emissions": 3.0, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "June"}	2026-01-11 15:36:54.451029+02	2026-01-11 15:36:54.451046+02	f	1	3	3	20
1199	{"waste_type": "Plastic", "quantity_kg": 182, "co2e_emissions": 105.56, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:54.457486+02	2026-01-11 15:36:54.457502+02	f	1	3	3	20
1200	{"waste_type": "Food Waste", "quantity_kg": 481, "co2e_emissions": 48.1, "reporting_year": 2023, "disposal_method": "Composted", "reporting_month": "June"}	2026-01-11 15:36:54.464155+02	2026-01-11 15:36:54.464176+02	f	1	3	3	20
1201	{"waste_type": "Food Waste", "quantity_kg": 529, "co2e_emissions": 306.82, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:54.472505+02	2026-01-11 15:36:54.472521+02	f	1	3	3	20
1202	{"waste_type": "E-Waste", "quantity_kg": 34, "co2e_emissions": 3.4, "reporting_year": 2023, "disposal_method": "Special Treatment", "reporting_month": "June"}	2026-01-11 15:36:54.477646+02	2026-01-11 15:36:54.477661+02	f	1	3	3	20
1203	{"waste_type": "General Waste", "quantity_kg": 850, "co2e_emissions": 493.0, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:54.481251+02	2026-01-11 15:36:54.481266+02	f	1	3	3	20
1204	{"waste_type": "Paper/Cardboard", "quantity_kg": 371, "co2e_emissions": 7.42, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "July"}	2026-01-11 15:36:54.484894+02	2026-01-11 15:36:54.484906+02	f	1	3	3	20
1205	{"waste_type": "Paper/Cardboard", "quantity_kg": 137, "co2e_emissions": 79.46, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:54.488675+02	2026-01-11 15:36:54.488691+02	f	1	3	3	20
1206	{"waste_type": "Plastic", "quantity_kg": 97, "co2e_emissions": 1.94, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "July"}	2026-01-11 15:36:54.492345+02	2026-01-11 15:36:54.49236+02	f	1	3	3	20
1207	{"waste_type": "Plastic", "quantity_kg": 114, "co2e_emissions": 66.12, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:54.497335+02	2026-01-11 15:36:54.49735+02	f	1	3	3	20
1208	{"waste_type": "Food Waste", "quantity_kg": 272, "co2e_emissions": 27.2, "reporting_year": 2023, "disposal_method": "Composted", "reporting_month": "July"}	2026-01-11 15:36:54.501259+02	2026-01-11 15:36:54.501276+02	f	1	3	3	20
1209	{"waste_type": "Food Waste", "quantity_kg": 310, "co2e_emissions": 179.8, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:54.505292+02	2026-01-11 15:36:54.505308+02	f	1	3	3	20
1210	{"waste_type": "E-Waste", "quantity_kg": 18, "co2e_emissions": 1.8, "reporting_year": 2023, "disposal_method": "Special Treatment", "reporting_month": "July"}	2026-01-11 15:36:54.508995+02	2026-01-11 15:36:54.509009+02	f	1	3	3	20
1211	{"waste_type": "General Waste", "quantity_kg": 658, "co2e_emissions": 381.64, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:54.51539+02	2026-01-11 15:36:54.515407+02	f	1	3	3	20
1212	{"waste_type": "Paper/Cardboard", "quantity_kg": 253, "co2e_emissions": 5.06, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "August"}	2026-01-11 15:36:54.520174+02	2026-01-11 15:36:54.520191+02	f	1	3	3	20
1213	{"waste_type": "Paper/Cardboard", "quantity_kg": 113, "co2e_emissions": 65.54, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:54.523946+02	2026-01-11 15:36:54.52396+02	f	1	3	3	20
1214	{"waste_type": "Plastic", "quantity_kg": 62, "co2e_emissions": 1.24, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "August"}	2026-01-11 15:36:54.527475+02	2026-01-11 15:36:54.52749+02	f	1	3	3	20
1215	{"waste_type": "Plastic", "quantity_kg": 88, "co2e_emissions": 51.04, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:54.531126+02	2026-01-11 15:36:54.53114+02	f	1	3	3	20
1216	{"waste_type": "Food Waste", "quantity_kg": 207, "co2e_emissions": 20.7, "reporting_year": 2023, "disposal_method": "Composted", "reporting_month": "August"}	2026-01-11 15:36:54.538247+02	2026-01-11 15:36:54.538263+02	f	1	3	3	20
1217	{"waste_type": "Food Waste", "quantity_kg": 250, "co2e_emissions": 145.0, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:54.543007+02	2026-01-11 15:36:54.543022+02	f	1	3	3	20
1218	{"waste_type": "E-Waste", "quantity_kg": 15, "co2e_emissions": 1.5, "reporting_year": 2023, "disposal_method": "Special Treatment", "reporting_month": "August"}	2026-01-11 15:36:54.546515+02	2026-01-11 15:36:54.546529+02	f	1	3	3	20
1219	{"waste_type": "General Waste", "quantity_kg": 2120, "co2e_emissions": 1229.6, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:54.550289+02	2026-01-11 15:36:54.550305+02	f	1	3	3	20
1220	{"waste_type": "Paper/Cardboard", "quantity_kg": 922, "co2e_emissions": 18.44, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "September"}	2026-01-11 15:36:54.553799+02	2026-01-11 15:36:54.553813+02	f	1	3	3	20
1221	{"waste_type": "Paper/Cardboard", "quantity_kg": 323, "co2e_emissions": 187.34, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:54.557427+02	2026-01-11 15:36:54.557443+02	f	1	3	3	20
1222	{"waste_type": "Plastic", "quantity_kg": 212, "co2e_emissions": 4.24, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "September"}	2026-01-11 15:36:54.560841+02	2026-01-11 15:36:54.560854+02	f	1	3	3	20
1223	{"waste_type": "Plastic", "quantity_kg": 247, "co2e_emissions": 143.26, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:54.564711+02	2026-01-11 15:36:54.56473+02	f	1	3	3	20
1224	{"waste_type": "Food Waste", "quantity_kg": 688, "co2e_emissions": 68.8, "reporting_year": 2023, "disposal_method": "Composted", "reporting_month": "September"}	2026-01-11 15:36:54.568335+02	2026-01-11 15:36:54.56835+02	f	1	3	3	20
1225	{"waste_type": "Food Waste", "quantity_kg": 759, "co2e_emissions": 440.22, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:54.571822+02	2026-01-11 15:36:54.571835+02	f	1	3	3	20
1226	{"waste_type": "E-Waste", "quantity_kg": 43, "co2e_emissions": 4.3, "reporting_year": 2023, "disposal_method": "Special Treatment", "reporting_month": "September"}	2026-01-11 15:36:54.574989+02	2026-01-11 15:36:54.575001+02	f	1	3	3	20
1227	{"waste_type": "General Waste", "quantity_kg": 2071, "co2e_emissions": 1201.18, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:54.578858+02	2026-01-11 15:36:54.578875+02	f	1	3	3	20
1228	{"waste_type": "Paper/Cardboard", "quantity_kg": 954, "co2e_emissions": 19.08, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "October"}	2026-01-11 15:36:54.584183+02	2026-01-11 15:36:54.584198+02	f	1	3	3	20
1229	{"waste_type": "Paper/Cardboard", "quantity_kg": 329, "co2e_emissions": 190.82, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:54.587734+02	2026-01-11 15:36:54.587747+02	f	1	3	3	20
1230	{"waste_type": "Plastic", "quantity_kg": 244, "co2e_emissions": 4.88, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "October"}	2026-01-11 15:36:54.591258+02	2026-01-11 15:36:54.59127+02	f	1	3	3	20
1231	{"waste_type": "Plastic", "quantity_kg": 263, "co2e_emissions": 152.54, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:54.595049+02	2026-01-11 15:36:54.595066+02	f	1	3	3	20
1232	{"waste_type": "Food Waste", "quantity_kg": 706, "co2e_emissions": 70.6, "reporting_year": 2023, "disposal_method": "Composted", "reporting_month": "October"}	2026-01-11 15:36:54.600193+02	2026-01-11 15:36:54.600208+02	f	1	3	3	20
1233	{"waste_type": "Food Waste", "quantity_kg": 853, "co2e_emissions": 494.74, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:54.603744+02	2026-01-11 15:36:54.603754+02	f	1	3	3	20
1234	{"waste_type": "E-Waste", "quantity_kg": 49, "co2e_emissions": 4.9, "reporting_year": 2023, "disposal_method": "Special Treatment", "reporting_month": "October"}	2026-01-11 15:36:54.607181+02	2026-01-11 15:36:54.607194+02	f	1	3	3	20
1235	{"waste_type": "General Waste", "quantity_kg": 2259, "co2e_emissions": 1310.22, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:54.610994+02	2026-01-11 15:36:54.611009+02	f	1	3	3	20
1236	{"waste_type": "Paper/Cardboard", "quantity_kg": 973, "co2e_emissions": 19.46, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "November"}	2026-01-11 15:36:54.614732+02	2026-01-11 15:36:54.614747+02	f	1	3	3	20
1237	{"waste_type": "Paper/Cardboard", "quantity_kg": 367, "co2e_emissions": 212.86, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:54.619369+02	2026-01-11 15:36:54.6194+02	f	1	3	3	20
1238	{"waste_type": "Plastic", "quantity_kg": 250, "co2e_emissions": 5.0, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "November"}	2026-01-11 15:36:54.623082+02	2026-01-11 15:36:54.623096+02	f	1	3	3	20
1239	{"waste_type": "Plastic", "quantity_kg": 275, "co2e_emissions": 159.5, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:54.628377+02	2026-01-11 15:36:54.628392+02	f	1	3	3	20
1240	{"waste_type": "Food Waste", "quantity_kg": 732, "co2e_emissions": 73.2, "reporting_year": 2023, "disposal_method": "Composted", "reporting_month": "November"}	2026-01-11 15:36:54.63318+02	2026-01-11 15:36:54.633195+02	f	1	3	3	20
1241	{"waste_type": "Food Waste", "quantity_kg": 891, "co2e_emissions": 516.78, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:54.637953+02	2026-01-11 15:36:54.637967+02	f	1	3	3	20
1242	{"waste_type": "E-Waste", "quantity_kg": 50, "co2e_emissions": 5.0, "reporting_year": 2023, "disposal_method": "Special Treatment", "reporting_month": "November"}	2026-01-11 15:36:54.641729+02	2026-01-11 15:36:54.641748+02	f	1	3	3	20
1243	{"waste_type": "General Waste", "quantity_kg": 1895, "co2e_emissions": 1099.1, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:54.64675+02	2026-01-11 15:36:54.646766+02	f	1	3	3	20
1244	{"waste_type": "Paper/Cardboard", "quantity_kg": 743, "co2e_emissions": 14.86, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "December"}	2026-01-11 15:36:54.650208+02	2026-01-11 15:36:54.650221+02	f	1	3	3	20
1245	{"waste_type": "Paper/Cardboard", "quantity_kg": 280, "co2e_emissions": 162.4, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:54.656749+02	2026-01-11 15:36:54.656766+02	f	1	3	3	20
1246	{"waste_type": "Plastic", "quantity_kg": 200, "co2e_emissions": 4.0, "reporting_year": 2023, "disposal_method": "Recycled", "reporting_month": "December"}	2026-01-11 15:36:54.660759+02	2026-01-11 15:36:54.660774+02	f	1	3	3	20
1247	{"waste_type": "Plastic", "quantity_kg": 211, "co2e_emissions": 122.38, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:54.664461+02	2026-01-11 15:36:54.664476+02	f	1	3	3	20
1248	{"waste_type": "Food Waste", "quantity_kg": 599, "co2e_emissions": 59.9, "reporting_year": 2023, "disposal_method": "Composted", "reporting_month": "December"}	2026-01-11 15:36:54.668074+02	2026-01-11 15:36:54.668087+02	f	1	3	3	20
1249	{"waste_type": "Food Waste", "quantity_kg": 742, "co2e_emissions": 430.36, "reporting_year": 2023, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:54.672169+02	2026-01-11 15:36:54.672189+02	f	1	3	3	20
1250	{"waste_type": "E-Waste", "quantity_kg": 45, "co2e_emissions": 4.5, "reporting_year": 2023, "disposal_method": "Special Treatment", "reporting_month": "December"}	2026-01-11 15:36:54.6772+02	2026-01-11 15:36:54.677216+02	f	1	3	3	20
1251	{"waste_type": "General Waste", "quantity_kg": 1798, "co2e_emissions": 1042.84, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:54.681112+02	2026-01-11 15:36:54.681126+02	f	1	3	3	20
1252	{"waste_type": "Paper/Cardboard", "quantity_kg": 796, "co2e_emissions": 15.92, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "January"}	2026-01-11 15:36:54.684673+02	2026-01-11 15:36:54.684685+02	f	1	3	3	20
1253	{"waste_type": "Paper/Cardboard", "quantity_kg": 324, "co2e_emissions": 187.92, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:54.689091+02	2026-01-11 15:36:54.689113+02	f	1	3	3	20
1254	{"waste_type": "Plastic", "quantity_kg": 221, "co2e_emissions": 4.42, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "January"}	2026-01-11 15:36:54.693381+02	2026-01-11 15:36:54.693397+02	f	1	3	3	20
1255	{"waste_type": "Plastic", "quantity_kg": 252, "co2e_emissions": 146.16, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:54.697111+02	2026-01-11 15:36:54.697124+02	f	1	3	3	20
1256	{"waste_type": "Food Waste", "quantity_kg": 698, "co2e_emissions": 69.8, "reporting_year": 2024, "disposal_method": "Composted", "reporting_month": "January"}	2026-01-11 15:36:54.700754+02	2026-01-11 15:36:54.700766+02	f	1	3	3	20
1257	{"waste_type": "Food Waste", "quantity_kg": 747, "co2e_emissions": 433.26, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "January"}	2026-01-11 15:36:54.705025+02	2026-01-11 15:36:54.70504+02	f	1	3	3	20
1258	{"waste_type": "E-Waste", "quantity_kg": 48, "co2e_emissions": 4.8, "reporting_year": 2024, "disposal_method": "Special Treatment", "reporting_month": "January"}	2026-01-11 15:36:54.70881+02	2026-01-11 15:36:54.708825+02	f	1	3	3	20
1259	{"waste_type": "General Waste", "quantity_kg": 2200, "co2e_emissions": 1276.0, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:54.713761+02	2026-01-11 15:36:54.713789+02	f	1	3	3	20
1260	{"waste_type": "Paper/Cardboard", "quantity_kg": 925, "co2e_emissions": 18.5, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "February"}	2026-01-11 15:36:54.717488+02	2026-01-11 15:36:54.717502+02	f	1	3	3	20
1261	{"waste_type": "Paper/Cardboard", "quantity_kg": 322, "co2e_emissions": 186.76, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:54.721997+02	2026-01-11 15:36:54.722014+02	f	1	3	3	20
1262	{"waste_type": "Plastic", "quantity_kg": 249, "co2e_emissions": 4.98, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "February"}	2026-01-11 15:36:54.726179+02	2026-01-11 15:36:54.726193+02	f	1	3	3	20
1263	{"waste_type": "Plastic", "quantity_kg": 238, "co2e_emissions": 138.04, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:54.732774+02	2026-01-11 15:36:54.732788+02	f	1	3	3	20
1264	{"waste_type": "Food Waste", "quantity_kg": 661, "co2e_emissions": 66.1, "reporting_year": 2024, "disposal_method": "Composted", "reporting_month": "February"}	2026-01-11 15:36:54.737895+02	2026-01-11 15:36:54.737912+02	f	1	3	3	20
1265	{"waste_type": "Food Waste", "quantity_kg": 787, "co2e_emissions": 456.46, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "February"}	2026-01-11 15:36:54.742612+02	2026-01-11 15:36:54.742634+02	f	1	3	3	20
1266	{"waste_type": "E-Waste", "quantity_kg": 54, "co2e_emissions": 5.4, "reporting_year": 2024, "disposal_method": "Special Treatment", "reporting_month": "February"}	2026-01-11 15:36:54.74621+02	2026-01-11 15:36:54.746223+02	f	1	3	3	20
1267	{"waste_type": "General Waste", "quantity_kg": 2177, "co2e_emissions": 1262.66, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:54.751786+02	2026-01-11 15:36:54.751802+02	f	1	3	3	20
1268	{"waste_type": "Paper/Cardboard", "quantity_kg": 1014, "co2e_emissions": 20.28, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "March"}	2026-01-11 15:36:54.755737+02	2026-01-11 15:36:54.755749+02	f	1	3	3	20
1269	{"waste_type": "Paper/Cardboard", "quantity_kg": 320, "co2e_emissions": 185.6, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:54.759336+02	2026-01-11 15:36:54.75935+02	f	1	3	3	20
1270	{"waste_type": "Plastic", "quantity_kg": 220, "co2e_emissions": 4.4, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "March"}	2026-01-11 15:36:54.765409+02	2026-01-11 15:36:54.765425+02	f	1	3	3	20
1271	{"waste_type": "Plastic", "quantity_kg": 263, "co2e_emissions": 152.54, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:54.769446+02	2026-01-11 15:36:54.769461+02	f	1	3	3	20
1272	{"waste_type": "Food Waste", "quantity_kg": 714, "co2e_emissions": 71.4, "reporting_year": 2024, "disposal_method": "Composted", "reporting_month": "March"}	2026-01-11 15:36:54.777028+02	2026-01-11 15:36:54.777047+02	f	1	3	3	20
1273	{"waste_type": "Food Waste", "quantity_kg": 725, "co2e_emissions": 420.5, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "March"}	2026-01-11 15:36:54.780638+02	2026-01-11 15:36:54.780655+02	f	1	3	3	20
1274	{"waste_type": "E-Waste", "quantity_kg": 51, "co2e_emissions": 5.1, "reporting_year": 2024, "disposal_method": "Special Treatment", "reporting_month": "March"}	2026-01-11 15:36:54.785539+02	2026-01-11 15:36:54.785565+02	f	1	3	3	20
1275	{"waste_type": "General Waste", "quantity_kg": 2371, "co2e_emissions": 1375.18, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:54.789399+02	2026-01-11 15:36:54.789413+02	f	1	3	3	20
1276	{"waste_type": "Paper/Cardboard", "quantity_kg": 998, "co2e_emissions": 19.96, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "April"}	2026-01-11 15:36:54.792936+02	2026-01-11 15:36:54.792949+02	f	1	3	3	20
1277	{"waste_type": "Paper/Cardboard", "quantity_kg": 384, "co2e_emissions": 222.72, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:54.797212+02	2026-01-11 15:36:54.797231+02	f	1	3	3	20
1278	{"waste_type": "Plastic", "quantity_kg": 241, "co2e_emissions": 4.82, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "April"}	2026-01-11 15:36:54.801333+02	2026-01-11 15:36:54.801348+02	f	1	3	3	20
1279	{"waste_type": "Plastic", "quantity_kg": 243, "co2e_emissions": 140.94, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:54.80509+02	2026-01-11 15:36:54.805103+02	f	1	3	3	20
1280	{"waste_type": "Food Waste", "quantity_kg": 788, "co2e_emissions": 78.8, "reporting_year": 2024, "disposal_method": "Composted", "reporting_month": "April"}	2026-01-11 15:36:54.808495+02	2026-01-11 15:36:54.808508+02	f	1	3	3	20
1281	{"waste_type": "Food Waste", "quantity_kg": 761, "co2e_emissions": 441.38, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "April"}	2026-01-11 15:36:54.812194+02	2026-01-11 15:36:54.812212+02	f	1	3	3	20
1282	{"waste_type": "E-Waste", "quantity_kg": 49, "co2e_emissions": 4.9, "reporting_year": 2024, "disposal_method": "Special Treatment", "reporting_month": "April"}	2026-01-11 15:36:54.816208+02	2026-01-11 15:36:54.816224+02	f	1	3	3	20
1283	{"waste_type": "General Waste", "quantity_kg": 1958, "co2e_emissions": 1135.64, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:54.820189+02	2026-01-11 15:36:54.820201+02	f	1	3	3	20
1284	{"waste_type": "Paper/Cardboard", "quantity_kg": 906, "co2e_emissions": 18.12, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "May"}	2026-01-11 15:36:54.823693+02	2026-01-11 15:36:54.823706+02	f	1	3	3	20
1285	{"waste_type": "Paper/Cardboard", "quantity_kg": 302, "co2e_emissions": 175.16, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:54.827584+02	2026-01-11 15:36:54.827643+02	f	1	3	3	20
1286	{"waste_type": "Plastic", "quantity_kg": 216, "co2e_emissions": 4.32, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "May"}	2026-01-11 15:36:54.831556+02	2026-01-11 15:36:54.831572+02	f	1	3	3	20
1287	{"waste_type": "Plastic", "quantity_kg": 233, "co2e_emissions": 135.14, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:54.835255+02	2026-01-11 15:36:54.835268+02	f	1	3	3	20
1288	{"waste_type": "Food Waste", "quantity_kg": 704, "co2e_emissions": 70.4, "reporting_year": 2024, "disposal_method": "Composted", "reporting_month": "May"}	2026-01-11 15:36:54.838809+02	2026-01-11 15:36:54.838821+02	f	1	3	3	20
1289	{"waste_type": "Food Waste", "quantity_kg": 679, "co2e_emissions": 393.82, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "May"}	2026-01-11 15:36:54.843763+02	2026-01-11 15:36:54.843781+02	f	1	3	3	20
1290	{"waste_type": "E-Waste", "quantity_kg": 45, "co2e_emissions": 4.5, "reporting_year": 2024, "disposal_method": "Special Treatment", "reporting_month": "May"}	2026-01-11 15:36:54.847742+02	2026-01-11 15:36:54.847757+02	f	1	3	3	20
1291	{"waste_type": "General Waste", "quantity_kg": 1421, "co2e_emissions": 824.18, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:54.851484+02	2026-01-11 15:36:54.851496+02	f	1	3	3	20
1292	{"waste_type": "Paper/Cardboard", "quantity_kg": 610, "co2e_emissions": 12.2, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "June"}	2026-01-11 15:36:54.85484+02	2026-01-11 15:36:54.854853+02	f	1	3	3	20
1293	{"waste_type": "Paper/Cardboard", "quantity_kg": 263, "co2e_emissions": 152.54, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:54.858695+02	2026-01-11 15:36:54.858725+02	f	1	3	3	20
1294	{"waste_type": "Plastic", "quantity_kg": 166, "co2e_emissions": 3.32, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "June"}	2026-01-11 15:36:54.864436+02	2026-01-11 15:36:54.864456+02	f	1	3	3	20
1295	{"waste_type": "Plastic", "quantity_kg": 175, "co2e_emissions": 101.5, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:54.868657+02	2026-01-11 15:36:54.868674+02	f	1	3	3	20
1296	{"waste_type": "Food Waste", "quantity_kg": 531, "co2e_emissions": 53.1, "reporting_year": 2024, "disposal_method": "Composted", "reporting_month": "June"}	2026-01-11 15:36:54.874129+02	2026-01-11 15:36:54.87415+02	f	1	3	3	20
1297	{"waste_type": "Food Waste", "quantity_kg": 590, "co2e_emissions": 342.2, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "June"}	2026-01-11 15:36:54.879758+02	2026-01-11 15:36:54.879776+02	f	1	3	3	20
1298	{"waste_type": "E-Waste", "quantity_kg": 34, "co2e_emissions": 3.4, "reporting_year": 2024, "disposal_method": "Special Treatment", "reporting_month": "June"}	2026-01-11 15:36:54.884073+02	2026-01-11 15:36:54.88409+02	f	1	3	3	20
1299	{"waste_type": "General Waste", "quantity_kg": 874, "co2e_emissions": 506.92, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:54.89027+02	2026-01-11 15:36:54.890305+02	f	1	3	3	20
1300	{"waste_type": "Paper/Cardboard", "quantity_kg": 393, "co2e_emissions": 7.86, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "July"}	2026-01-11 15:36:54.895422+02	2026-01-11 15:36:54.895439+02	f	1	3	3	20
1301	{"waste_type": "Paper/Cardboard", "quantity_kg": 139, "co2e_emissions": 80.62, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:54.899751+02	2026-01-11 15:36:54.899769+02	f	1	3	3	20
1302	{"waste_type": "Plastic", "quantity_kg": 96, "co2e_emissions": 1.92, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "July"}	2026-01-11 15:36:54.903902+02	2026-01-11 15:36:54.90392+02	f	1	3	3	20
1303	{"waste_type": "Plastic", "quantity_kg": 112, "co2e_emissions": 64.96, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:54.908889+02	2026-01-11 15:36:54.908905+02	f	1	3	3	20
1304	{"waste_type": "Food Waste", "quantity_kg": 280, "co2e_emissions": 28.0, "reporting_year": 2024, "disposal_method": "Composted", "reporting_month": "July"}	2026-01-11 15:36:54.912685+02	2026-01-11 15:36:54.912699+02	f	1	3	3	20
1305	{"waste_type": "Food Waste", "quantity_kg": 300, "co2e_emissions": 174.0, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "July"}	2026-01-11 15:36:54.916529+02	2026-01-11 15:36:54.916542+02	f	1	3	3	20
1306	{"waste_type": "E-Waste", "quantity_kg": 21, "co2e_emissions": 2.1, "reporting_year": 2024, "disposal_method": "Special Treatment", "reporting_month": "July"}	2026-01-11 15:36:54.920028+02	2026-01-11 15:36:54.920045+02	f	1	3	3	20
1307	{"waste_type": "General Waste", "quantity_kg": 649, "co2e_emissions": 376.42, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:54.924081+02	2026-01-11 15:36:54.924095+02	f	1	3	3	20
1308	{"waste_type": "Paper/Cardboard", "quantity_kg": 311, "co2e_emissions": 6.22, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "August"}	2026-01-11 15:36:54.927644+02	2026-01-11 15:36:54.927657+02	f	1	3	3	20
1309	{"waste_type": "Paper/Cardboard", "quantity_kg": 111, "co2e_emissions": 64.38, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:54.931539+02	2026-01-11 15:36:54.931553+02	f	1	3	3	20
1310	{"waste_type": "Plastic", "quantity_kg": 76, "co2e_emissions": 1.52, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "August"}	2026-01-11 15:36:54.936632+02	2026-01-11 15:36:54.936655+02	f	1	3	3	20
1311	{"waste_type": "Plastic", "quantity_kg": 76, "co2e_emissions": 44.08, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:54.942152+02	2026-01-11 15:36:54.942166+02	f	1	3	3	20
1312	{"waste_type": "Food Waste", "quantity_kg": 202, "co2e_emissions": 20.2, "reporting_year": 2024, "disposal_method": "Composted", "reporting_month": "August"}	2026-01-11 15:36:54.945969+02	2026-01-11 15:36:54.945982+02	f	1	3	3	20
1313	{"waste_type": "Food Waste", "quantity_kg": 226, "co2e_emissions": 131.08, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "August"}	2026-01-11 15:36:54.949417+02	2026-01-11 15:36:54.94943+02	f	1	3	3	20
1314	{"waste_type": "E-Waste", "quantity_kg": 14, "co2e_emissions": 1.4, "reporting_year": 2024, "disposal_method": "Special Treatment", "reporting_month": "August"}	2026-01-11 15:36:54.953072+02	2026-01-11 15:36:54.953087+02	f	1	3	3	20
1315	{"waste_type": "General Waste", "quantity_kg": 2295, "co2e_emissions": 1331.1, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:54.956823+02	2026-01-11 15:36:54.956838+02	f	1	3	3	20
1316	{"waste_type": "Paper/Cardboard", "quantity_kg": 983, "co2e_emissions": 19.66, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "September"}	2026-01-11 15:36:54.961646+02	2026-01-11 15:36:54.961659+02	f	1	3	3	20
1317	{"waste_type": "Paper/Cardboard", "quantity_kg": 362, "co2e_emissions": 209.96, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:54.966269+02	2026-01-11 15:36:54.966283+02	f	1	3	3	20
1318	{"waste_type": "Plastic", "quantity_kg": 223, "co2e_emissions": 4.46, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "September"}	2026-01-11 15:36:54.97038+02	2026-01-11 15:36:54.970396+02	f	1	3	3	20
1319	{"waste_type": "Plastic", "quantity_kg": 275, "co2e_emissions": 159.5, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:54.973947+02	2026-01-11 15:36:54.97396+02	f	1	3	3	20
1320	{"waste_type": "Food Waste", "quantity_kg": 708, "co2e_emissions": 70.8, "reporting_year": 2024, "disposal_method": "Composted", "reporting_month": "September"}	2026-01-11 15:36:54.978495+02	2026-01-11 15:36:54.978508+02	f	1	3	3	20
1321	{"waste_type": "Food Waste", "quantity_kg": 780, "co2e_emissions": 452.4, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "September"}	2026-01-11 15:36:54.982135+02	2026-01-11 15:36:54.982151+02	f	1	3	3	20
1322	{"waste_type": "E-Waste", "quantity_kg": 51, "co2e_emissions": 5.1, "reporting_year": 2024, "disposal_method": "Special Treatment", "reporting_month": "September"}	2026-01-11 15:36:54.986874+02	2026-01-11 15:36:54.986889+02	f	1	3	3	20
1323	{"waste_type": "General Waste", "quantity_kg": 2411, "co2e_emissions": 1398.38, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:54.990773+02	2026-01-11 15:36:54.990787+02	f	1	3	3	20
1324	{"waste_type": "Paper/Cardboard", "quantity_kg": 1001, "co2e_emissions": 20.02, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "October"}	2026-01-11 15:36:54.994305+02	2026-01-11 15:36:54.994316+02	f	1	3	3	20
1325	{"waste_type": "Paper/Cardboard", "quantity_kg": 369, "co2e_emissions": 214.02, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:54.997818+02	2026-01-11 15:36:54.997842+02	f	1	3	3	20
1326	{"waste_type": "Plastic", "quantity_kg": 229, "co2e_emissions": 4.58, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "October"}	2026-01-11 15:36:55.001755+02	2026-01-11 15:36:55.001771+02	f	1	3	3	20
1327	{"waste_type": "Plastic", "quantity_kg": 279, "co2e_emissions": 161.82, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:55.006433+02	2026-01-11 15:36:55.006447+02	f	1	3	3	20
1328	{"waste_type": "Food Waste", "quantity_kg": 750, "co2e_emissions": 75.0, "reporting_year": 2024, "disposal_method": "Composted", "reporting_month": "October"}	2026-01-11 15:36:55.011408+02	2026-01-11 15:36:55.01142+02	f	1	3	3	20
1329	{"waste_type": "Food Waste", "quantity_kg": 791, "co2e_emissions": 458.78, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "October"}	2026-01-11 15:36:55.015185+02	2026-01-11 15:36:55.0152+02	f	1	3	3	20
1330	{"waste_type": "E-Waste", "quantity_kg": 49, "co2e_emissions": 4.9, "reporting_year": 2024, "disposal_method": "Special Treatment", "reporting_month": "October"}	2026-01-11 15:36:55.019004+02	2026-01-11 15:36:55.019019+02	f	1	3	3	20
1331	{"waste_type": "General Waste", "quantity_kg": 2345, "co2e_emissions": 1360.1, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:55.022775+02	2026-01-11 15:36:55.02279+02	f	1	3	3	20
1332	{"waste_type": "Paper/Cardboard", "quantity_kg": 953, "co2e_emissions": 19.06, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "November"}	2026-01-11 15:36:55.02637+02	2026-01-11 15:36:55.026385+02	f	1	3	3	20
1333	{"waste_type": "Paper/Cardboard", "quantity_kg": 319, "co2e_emissions": 185.02, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:55.030635+02	2026-01-11 15:36:55.030651+02	f	1	3	3	20
1334	{"waste_type": "Plastic", "quantity_kg": 233, "co2e_emissions": 4.66, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "November"}	2026-01-11 15:36:55.034276+02	2026-01-11 15:36:55.03429+02	f	1	3	3	20
1335	{"waste_type": "Plastic", "quantity_kg": 250, "co2e_emissions": 145.0, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:55.037867+02	2026-01-11 15:36:55.037881+02	f	1	3	3	20
1336	{"waste_type": "Food Waste", "quantity_kg": 706, "co2e_emissions": 70.6, "reporting_year": 2024, "disposal_method": "Composted", "reporting_month": "November"}	2026-01-11 15:36:55.043685+02	2026-01-11 15:36:55.043698+02	f	1	3	3	20
1337	{"waste_type": "Food Waste", "quantity_kg": 748, "co2e_emissions": 433.84, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "November"}	2026-01-11 15:36:55.048694+02	2026-01-11 15:36:55.04871+02	f	1	3	3	20
1338	{"waste_type": "E-Waste", "quantity_kg": 48, "co2e_emissions": 4.8, "reporting_year": 2024, "disposal_method": "Special Treatment", "reporting_month": "November"}	2026-01-11 15:36:55.052326+02	2026-01-11 15:36:55.05234+02	f	1	3	3	20
1339	{"waste_type": "General Waste", "quantity_kg": 1721, "co2e_emissions": 998.18, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:55.056007+02	2026-01-11 15:36:55.056022+02	f	1	3	3	20
1340	{"waste_type": "Paper/Cardboard", "quantity_kg": 895, "co2e_emissions": 17.9, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "December"}	2026-01-11 15:36:55.059753+02	2026-01-11 15:36:55.059773+02	f	1	3	3	20
1341	{"waste_type": "Paper/Cardboard", "quantity_kg": 285, "co2e_emissions": 165.3, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:55.069818+02	2026-01-11 15:36:55.069834+02	f	1	3	3	20
1342	{"waste_type": "Plastic", "quantity_kg": 210, "co2e_emissions": 4.2, "reporting_year": 2024, "disposal_method": "Recycled", "reporting_month": "December"}	2026-01-11 15:36:55.073568+02	2026-01-11 15:36:55.073583+02	f	1	3	3	20
1343	{"waste_type": "Plastic", "quantity_kg": 202, "co2e_emissions": 117.16, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:55.077729+02	2026-01-11 15:36:55.077758+02	f	1	3	3	20
1344	{"waste_type": "Food Waste", "quantity_kg": 589, "co2e_emissions": 58.9, "reporting_year": 2024, "disposal_method": "Composted", "reporting_month": "December"}	2026-01-11 15:36:55.082931+02	2026-01-11 15:36:55.082946+02	f	1	3	3	20
1345	{"waste_type": "Food Waste", "quantity_kg": 614, "co2e_emissions": 356.12, "reporting_year": 2024, "disposal_method": "Landfill", "reporting_month": "December"}	2026-01-11 15:36:55.087578+02	2026-01-11 15:36:55.087593+02	f	1	3	3	20
1346	{"waste_type": "E-Waste", "quantity_kg": 42, "co2e_emissions": 4.2, "reporting_year": 2024, "disposal_method": "Special Treatment", "reporting_month": "December"}	2026-01-11 15:36:55.09264+02	2026-01-11 15:36:55.092656+02	f	1	3	3	20
1347	{"purpose": "Conference", "quarter": "Q1", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2020, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.154474+02	2026-01-11 15:36:55.154491+02	f	1	3	3	21
1348	{"purpose": "Administrative", "quarter": "Q1", "total_km": 800, "travel_type": "Domestic", "co2e_emissions": 204.0, "reporting_year": 2020, "avg_distance_km": 400, "number_of_trips": 1}	2026-01-11 15:36:55.158319+02	2026-01-11 15:36:55.158334+02	f	1	3	3	21
1349	{"purpose": "Conference", "quarter": "Q1", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2020, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.161978+02	2026-01-11 15:36:55.161992+02	f	1	3	3	21
1350	{"purpose": "Research Collaboration", "quarter": "Q1", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2020, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.16548+02	2026-01-11 15:36:55.165493+02	f	1	3	3	21
1351	{"purpose": "Conference", "quarter": "Q1", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2020, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.169344+02	2026-01-11 15:36:55.169361+02	f	1	3	3	21
1352	{"purpose": "Research Collaboration", "quarter": "Q1", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2020, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.17573+02	2026-01-11 15:36:55.175759+02	f	1	3	3	21
1353	{"purpose": "Training", "quarter": "Q1", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2020, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.17957+02	2026-01-11 15:36:55.179584+02	f	1	3	3	21
1354	{"purpose": "Conference", "quarter": "Q2", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2020, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.183617+02	2026-01-11 15:36:55.183643+02	f	1	3	3	21
1355	{"purpose": "Administrative", "quarter": "Q2", "total_km": 800, "travel_type": "Domestic", "co2e_emissions": 204.0, "reporting_year": 2020, "avg_distance_km": 400, "number_of_trips": 1}	2026-01-11 15:36:55.18778+02	2026-01-11 15:36:55.187795+02	f	1	3	3	21
1356	{"purpose": "Conference", "quarter": "Q2", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2020, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.191531+02	2026-01-11 15:36:55.191546+02	f	1	3	3	21
1357	{"purpose": "Research Collaboration", "quarter": "Q2", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2020, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.197879+02	2026-01-11 15:36:55.197893+02	f	1	3	3	21
1358	{"purpose": "Conference", "quarter": "Q2", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2020, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.201747+02	2026-01-11 15:36:55.201764+02	f	1	3	3	21
1359	{"purpose": "Research Collaboration", "quarter": "Q2", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2020, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.205753+02	2026-01-11 15:36:55.205768+02	f	1	3	3	21
1360	{"purpose": "Training", "quarter": "Q2", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2020, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.209552+02	2026-01-11 15:36:55.209567+02	f	1	3	3	21
1361	{"purpose": "Conference", "quarter": "Q3", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2020, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.214907+02	2026-01-11 15:36:55.214927+02	f	1	3	3	21
1362	{"purpose": "Administrative", "quarter": "Q3", "total_km": 800, "travel_type": "Domestic", "co2e_emissions": 204.0, "reporting_year": 2020, "avg_distance_km": 400, "number_of_trips": 1}	2026-01-11 15:36:55.219911+02	2026-01-11 15:36:55.219926+02	f	1	3	3	21
1363	{"purpose": "Conference", "quarter": "Q3", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2020, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.223557+02	2026-01-11 15:36:55.223571+02	f	1	3	3	21
1364	{"purpose": "Research Collaboration", "quarter": "Q3", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2020, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.227391+02	2026-01-11 15:36:55.227403+02	f	1	3	3	21
1365	{"purpose": "Conference", "quarter": "Q3", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2020, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.231329+02	2026-01-11 15:36:55.231347+02	f	1	3	3	21
1366	{"purpose": "Research Collaboration", "quarter": "Q3", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2020, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.235219+02	2026-01-11 15:36:55.235234+02	f	1	3	3	21
1367	{"purpose": "Training", "quarter": "Q3", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2020, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.239208+02	2026-01-11 15:36:55.239222+02	f	1	3	3	21
1368	{"purpose": "Conference", "quarter": "Q4", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2020, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.242933+02	2026-01-11 15:36:55.242947+02	f	1	3	3	21
1369	{"purpose": "Administrative", "quarter": "Q4", "total_km": 800, "travel_type": "Domestic", "co2e_emissions": 204.0, "reporting_year": 2020, "avg_distance_km": 400, "number_of_trips": 1}	2026-01-11 15:36:55.246514+02	2026-01-11 15:36:55.24653+02	f	1	3	3	21
1370	{"purpose": "Conference", "quarter": "Q4", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2020, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.250456+02	2026-01-11 15:36:55.250471+02	f	1	3	3	21
1371	{"purpose": "Research Collaboration", "quarter": "Q4", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2020, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.254196+02	2026-01-11 15:36:55.254208+02	f	1	3	3	21
1372	{"purpose": "Conference", "quarter": "Q4", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2020, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.258672+02	2026-01-11 15:36:55.258686+02	f	1	3	3	21
1373	{"purpose": "Research Collaboration", "quarter": "Q4", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2020, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.262409+02	2026-01-11 15:36:55.262427+02	f	1	3	3	21
1374	{"purpose": "Training", "quarter": "Q4", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2020, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.266298+02	2026-01-11 15:36:55.266313+02	f	1	3	3	21
1375	{"purpose": "Conference", "quarter": "Q1", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2021, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.269888+02	2026-01-11 15:36:55.269898+02	f	1	3	3	21
1376	{"purpose": "Administrative", "quarter": "Q1", "total_km": 800, "travel_type": "Domestic", "co2e_emissions": 204.0, "reporting_year": 2021, "avg_distance_km": 400, "number_of_trips": 1}	2026-01-11 15:36:55.273445+02	2026-01-11 15:36:55.273457+02	f	1	3	3	21
1377	{"purpose": "Conference", "quarter": "Q1", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2021, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.278546+02	2026-01-11 15:36:55.278564+02	f	1	3	3	21
1378	{"purpose": "Research Collaboration", "quarter": "Q1", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2021, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.282528+02	2026-01-11 15:36:55.282543+02	f	1	3	3	21
1379	{"purpose": "Conference", "quarter": "Q1", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2021, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.286058+02	2026-01-11 15:36:55.286069+02	f	1	3	3	21
1380	{"purpose": "Research Collaboration", "quarter": "Q1", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2021, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.290947+02	2026-01-11 15:36:55.290962+02	f	1	3	3	21
1381	{"purpose": "Training", "quarter": "Q1", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2021, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.29612+02	2026-01-11 15:36:55.296136+02	f	1	3	3	21
1382	{"purpose": "Conference", "quarter": "Q2", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2021, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.299732+02	2026-01-11 15:36:55.299746+02	f	1	3	3	21
1383	{"purpose": "Administrative", "quarter": "Q2", "total_km": 800, "travel_type": "Domestic", "co2e_emissions": 204.0, "reporting_year": 2021, "avg_distance_km": 400, "number_of_trips": 1}	2026-01-11 15:36:55.30435+02	2026-01-11 15:36:55.304365+02	f	1	3	3	21
1384	{"purpose": "Conference", "quarter": "Q2", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2021, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.310165+02	2026-01-11 15:36:55.310191+02	f	1	3	3	21
1385	{"purpose": "Research Collaboration", "quarter": "Q2", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2021, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.314245+02	2026-01-11 15:36:55.314259+02	f	1	3	3	21
1386	{"purpose": "Conference", "quarter": "Q2", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2021, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.318709+02	2026-01-11 15:36:55.318723+02	f	1	3	3	21
1387	{"purpose": "Research Collaboration", "quarter": "Q2", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2021, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.322278+02	2026-01-11 15:36:55.322292+02	f	1	3	3	21
1388	{"purpose": "Training", "quarter": "Q2", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2021, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.326117+02	2026-01-11 15:36:55.326133+02	f	1	3	3	21
1389	{"purpose": "Conference", "quarter": "Q3", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2021, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.331158+02	2026-01-11 15:36:55.331172+02	f	1	3	3	21
1390	{"purpose": "Administrative", "quarter": "Q3", "total_km": 800, "travel_type": "Domestic", "co2e_emissions": 204.0, "reporting_year": 2021, "avg_distance_km": 400, "number_of_trips": 1}	2026-01-11 15:36:55.334693+02	2026-01-11 15:36:55.334706+02	f	1	3	3	21
1391	{"purpose": "Conference", "quarter": "Q3", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2021, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.338107+02	2026-01-11 15:36:55.338118+02	f	1	3	3	21
1392	{"purpose": "Research Collaboration", "quarter": "Q3", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2021, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.341774+02	2026-01-11 15:36:55.341789+02	f	1	3	3	21
1393	{"purpose": "Conference", "quarter": "Q3", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2021, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.345509+02	2026-01-11 15:36:55.345529+02	f	1	3	3	21
1394	{"purpose": "Research Collaboration", "quarter": "Q3", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2021, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.349186+02	2026-01-11 15:36:55.349199+02	f	1	3	3	21
1395	{"purpose": "Training", "quarter": "Q3", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2021, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.352782+02	2026-01-11 15:36:55.352796+02	f	1	3	3	21
1396	{"purpose": "Conference", "quarter": "Q4", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2021, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.356545+02	2026-01-11 15:36:55.356561+02	f	1	3	3	21
1397	{"purpose": "Administrative", "quarter": "Q4", "total_km": 800, "travel_type": "Domestic", "co2e_emissions": 204.0, "reporting_year": 2021, "avg_distance_km": 400, "number_of_trips": 1}	2026-01-11 15:36:55.360428+02	2026-01-11 15:36:55.360443+02	f	1	3	3	21
1398	{"purpose": "Conference", "quarter": "Q4", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2021, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.365275+02	2026-01-11 15:36:55.365289+02	f	1	3	3	21
1399	{"purpose": "Research Collaboration", "quarter": "Q4", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2021, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.3691+02	2026-01-11 15:36:55.369113+02	f	1	3	3	21
1400	{"purpose": "Conference", "quarter": "Q4", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2021, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.373238+02	2026-01-11 15:36:55.373254+02	f	1	3	3	21
1401	{"purpose": "Research Collaboration", "quarter": "Q4", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2021, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.377072+02	2026-01-11 15:36:55.377086+02	f	1	3	3	21
1402	{"purpose": "Training", "quarter": "Q4", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2021, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.380563+02	2026-01-11 15:36:55.380577+02	f	1	3	3	21
1403	{"purpose": "Conference", "quarter": "Q1", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2022, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.384361+02	2026-01-11 15:36:55.384373+02	f	1	3	3	21
1404	{"purpose": "Administrative", "quarter": "Q1", "total_km": 1600, "travel_type": "Domestic", "co2e_emissions": 408.0, "reporting_year": 2022, "avg_distance_km": 400, "number_of_trips": 2}	2026-01-11 15:36:55.388152+02	2026-01-11 15:36:55.388174+02	f	1	3	3	21
1405	{"purpose": "Conference", "quarter": "Q1", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2022, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.392101+02	2026-01-11 15:36:55.392116+02	f	1	3	3	21
1406	{"purpose": "Research Collaboration", "quarter": "Q1", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2022, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.395589+02	2026-01-11 15:36:55.395604+02	f	1	3	3	21
1407	{"purpose": "Conference", "quarter": "Q1", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2022, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.399207+02	2026-01-11 15:36:55.399221+02	f	1	3	3	21
1408	{"purpose": "Research Collaboration", "quarter": "Q1", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2022, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.404752+02	2026-01-11 15:36:55.404767+02	f	1	3	3	21
1409	{"purpose": "Training", "quarter": "Q1", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2022, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.408467+02	2026-01-11 15:36:55.40848+02	f	1	3	3	21
1410	{"purpose": "Conference", "quarter": "Q2", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2022, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.413325+02	2026-01-11 15:36:55.413339+02	f	1	3	3	21
1411	{"purpose": "Administrative", "quarter": "Q2", "total_km": 1600, "travel_type": "Domestic", "co2e_emissions": 408.0, "reporting_year": 2022, "avg_distance_km": 400, "number_of_trips": 2}	2026-01-11 15:36:55.417341+02	2026-01-11 15:36:55.417357+02	f	1	3	3	21
1412	{"purpose": "Conference", "quarter": "Q2", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2022, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.421174+02	2026-01-11 15:36:55.42119+02	f	1	3	3	21
1413	{"purpose": "Research Collaboration", "quarter": "Q2", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2022, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.424965+02	2026-01-11 15:36:55.424981+02	f	1	3	3	21
1414	{"purpose": "Conference", "quarter": "Q2", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2022, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.428511+02	2026-01-11 15:36:55.428524+02	f	1	3	3	21
1415	{"purpose": "Research Collaboration", "quarter": "Q2", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2022, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.433568+02	2026-01-11 15:36:55.433585+02	f	1	3	3	21
1416	{"purpose": "Training", "quarter": "Q2", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2022, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.437691+02	2026-01-11 15:36:55.437706+02	f	1	3	3	21
1417	{"purpose": "Conference", "quarter": "Q3", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2022, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.441507+02	2026-01-11 15:36:55.44152+02	f	1	3	3	21
1418	{"purpose": "Administrative", "quarter": "Q3", "total_km": 800, "travel_type": "Domestic", "co2e_emissions": 204.0, "reporting_year": 2022, "avg_distance_km": 400, "number_of_trips": 1}	2026-01-11 15:36:55.445146+02	2026-01-11 15:36:55.445158+02	f	1	3	3	21
1419	{"purpose": "Conference", "quarter": "Q3", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2022, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.450082+02	2026-01-11 15:36:55.450097+02	f	1	3	3	21
1420	{"purpose": "Research Collaboration", "quarter": "Q3", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2022, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.453998+02	2026-01-11 15:36:55.454012+02	f	1	3	3	21
1421	{"purpose": "Conference", "quarter": "Q3", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2022, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.457609+02	2026-01-11 15:36:55.457623+02	f	1	3	3	21
1422	{"purpose": "Research Collaboration", "quarter": "Q3", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2022, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.461162+02	2026-01-11 15:36:55.461174+02	f	1	3	3	21
1423	{"purpose": "Training", "quarter": "Q3", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2022, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.465121+02	2026-01-11 15:36:55.465138+02	f	1	3	3	21
1424	{"purpose": "Conference", "quarter": "Q4", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2022, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.468951+02	2026-01-11 15:36:55.468966+02	f	1	3	3	21
1425	{"purpose": "Administrative", "quarter": "Q4", "total_km": 1600, "travel_type": "Domestic", "co2e_emissions": 408.0, "reporting_year": 2022, "avg_distance_km": 400, "number_of_trips": 2}	2026-01-11 15:36:55.472439+02	2026-01-11 15:36:55.472452+02	f	1	3	3	21
1426	{"purpose": "Conference", "quarter": "Q4", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2022, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.475988+02	2026-01-11 15:36:55.476002+02	f	1	3	3	21
1427	{"purpose": "Research Collaboration", "quarter": "Q4", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2022, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.479746+02	2026-01-11 15:36:55.479761+02	f	1	3	3	21
1428	{"purpose": "Conference", "quarter": "Q4", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2022, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.484789+02	2026-01-11 15:36:55.484806+02	f	1	3	3	21
1429	{"purpose": "Research Collaboration", "quarter": "Q4", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2022, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.48891+02	2026-01-11 15:36:55.488926+02	f	1	3	3	21
1430	{"purpose": "Training", "quarter": "Q4", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2022, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.492532+02	2026-01-11 15:36:55.492547+02	f	1	3	3	21
1431	{"purpose": "Conference", "quarter": "Q1", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2023, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.496497+02	2026-01-11 15:36:55.496512+02	f	1	3	3	21
1432	{"purpose": "Administrative", "quarter": "Q1", "total_km": 2400, "travel_type": "Domestic", "co2e_emissions": 612.0, "reporting_year": 2023, "avg_distance_km": 400, "number_of_trips": 3}	2026-01-11 15:36:55.501689+02	2026-01-11 15:36:55.501703+02	f	1	3	3	21
1433	{"purpose": "Conference", "quarter": "Q1", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2023, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.505367+02	2026-01-11 15:36:55.50538+02	f	1	3	3	21
1434	{"purpose": "Research Collaboration", "quarter": "Q1", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2023, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.508612+02	2026-01-11 15:36:55.508626+02	f	1	3	3	21
1435	{"purpose": "Conference", "quarter": "Q1", "total_km": 20000, "travel_type": "International", "co2e_emissions": 3900.0, "reporting_year": 2023, "avg_distance_km": 5000, "number_of_trips": 2}	2026-01-11 15:36:55.512215+02	2026-01-11 15:36:55.51223+02	f	1	3	3	21
1436	{"purpose": "Research Collaboration", "quarter": "Q1", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2023, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.517241+02	2026-01-11 15:36:55.517255+02	f	1	3	3	21
1437	{"purpose": "Training", "quarter": "Q1", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2023, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.520806+02	2026-01-11 15:36:55.520819+02	f	1	3	3	21
1438	{"purpose": "Conference", "quarter": "Q2", "total_km": 2000, "travel_type": "Domestic", "co2e_emissions": 510.0, "reporting_year": 2023, "avg_distance_km": 500, "number_of_trips": 2}	2026-01-11 15:36:55.524186+02	2026-01-11 15:36:55.524199+02	f	1	3	3	21
1439	{"purpose": "Administrative", "quarter": "Q2", "total_km": 1600, "travel_type": "Domestic", "co2e_emissions": 408.0, "reporting_year": 2023, "avg_distance_km": 400, "number_of_trips": 2}	2026-01-11 15:36:55.528789+02	2026-01-11 15:36:55.528807+02	f	1	3	3	21
1440	{"purpose": "Conference", "quarter": "Q2", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2023, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.532835+02	2026-01-11 15:36:55.532848+02	f	1	3	3	21
1441	{"purpose": "Research Collaboration", "quarter": "Q2", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2023, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.536738+02	2026-01-11 15:36:55.536753+02	f	1	3	3	21
1442	{"purpose": "Conference", "quarter": "Q2", "total_km": 20000, "travel_type": "International", "co2e_emissions": 3900.0, "reporting_year": 2023, "avg_distance_km": 5000, "number_of_trips": 2}	2026-01-11 15:36:55.540164+02	2026-01-11 15:36:55.540175+02	f	1	3	3	21
1443	{"purpose": "Research Collaboration", "quarter": "Q2", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2023, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.544512+02	2026-01-11 15:36:55.544527+02	f	1	3	3	21
1444	{"purpose": "Training", "quarter": "Q2", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2023, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.548115+02	2026-01-11 15:36:55.548129+02	f	1	3	3	21
1445	{"purpose": "Conference", "quarter": "Q3", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2023, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.55179+02	2026-01-11 15:36:55.551803+02	f	1	3	3	21
1446	{"purpose": "Administrative", "quarter": "Q3", "total_km": 1600, "travel_type": "Domestic", "co2e_emissions": 408.0, "reporting_year": 2023, "avg_distance_km": 400, "number_of_trips": 2}	2026-01-11 15:36:55.555227+02	2026-01-11 15:36:55.555241+02	f	1	3	3	21
1447	{"purpose": "Conference", "quarter": "Q3", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2023, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.559119+02	2026-01-11 15:36:55.559135+02	f	1	3	3	21
1448	{"purpose": "Research Collaboration", "quarter": "Q3", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2023, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.562834+02	2026-01-11 15:36:55.562847+02	f	1	3	3	21
1449	{"purpose": "Conference", "quarter": "Q3", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2023, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.566687+02	2026-01-11 15:36:55.566701+02	f	1	3	3	21
1450	{"purpose": "Research Collaboration", "quarter": "Q3", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2023, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.570213+02	2026-01-11 15:36:55.570226+02	f	1	3	3	21
1451	{"purpose": "Training", "quarter": "Q3", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2023, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.573967+02	2026-01-11 15:36:55.573982+02	f	1	3	3	21
1452	{"purpose": "Conference", "quarter": "Q4", "total_km": 2000, "travel_type": "Domestic", "co2e_emissions": 510.0, "reporting_year": 2023, "avg_distance_km": 500, "number_of_trips": 2}	2026-01-11 15:36:55.58057+02	2026-01-11 15:36:55.580585+02	f	1	3	3	21
1453	{"purpose": "Administrative", "quarter": "Q4", "total_km": 2400, "travel_type": "Domestic", "co2e_emissions": 612.0, "reporting_year": 2023, "avg_distance_km": 400, "number_of_trips": 3}	2026-01-11 15:36:55.584468+02	2026-01-11 15:36:55.584479+02	f	1	3	3	21
1454	{"purpose": "Conference", "quarter": "Q4", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2023, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.588218+02	2026-01-11 15:36:55.588233+02	f	1	3	3	21
1455	{"purpose": "Research Collaboration", "quarter": "Q4", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2023, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.592092+02	2026-01-11 15:36:55.592106+02	f	1	3	3	21
1456	{"purpose": "Conference", "quarter": "Q4", "total_km": 20000, "travel_type": "International", "co2e_emissions": 3900.0, "reporting_year": 2023, "avg_distance_km": 5000, "number_of_trips": 2}	2026-01-11 15:36:55.599034+02	2026-01-11 15:36:55.599048+02	f	1	3	3	21
1457	{"purpose": "Research Collaboration", "quarter": "Q4", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2023, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.603147+02	2026-01-11 15:36:55.603164+02	f	1	3	3	21
1458	{"purpose": "Training", "quarter": "Q4", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2023, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.607056+02	2026-01-11 15:36:55.607072+02	f	1	3	3	21
1459	{"purpose": "Conference", "quarter": "Q1", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2024, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.610796+02	2026-01-11 15:36:55.610807+02	f	1	3	3	21
1460	{"purpose": "Administrative", "quarter": "Q1", "total_km": 2400, "travel_type": "Domestic", "co2e_emissions": 612.0, "reporting_year": 2024, "avg_distance_km": 400, "number_of_trips": 3}	2026-01-11 15:36:55.614247+02	2026-01-11 15:36:55.614259+02	f	1	3	3	21
1461	{"purpose": "Conference", "quarter": "Q1", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2024, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.617734+02	2026-01-11 15:36:55.617747+02	f	1	3	3	21
1462	{"purpose": "Research Collaboration", "quarter": "Q1", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2024, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.621671+02	2026-01-11 15:36:55.621687+02	f	1	3	3	21
1463	{"purpose": "Conference", "quarter": "Q1", "total_km": 20000, "travel_type": "International", "co2e_emissions": 3900.0, "reporting_year": 2024, "avg_distance_km": 5000, "number_of_trips": 2}	2026-01-11 15:36:55.625473+02	2026-01-11 15:36:55.625486+02	f	1	3	3	21
1464	{"purpose": "Research Collaboration", "quarter": "Q1", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2024, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.630942+02	2026-01-11 15:36:55.630958+02	f	1	3	3	21
1465	{"purpose": "Training", "quarter": "Q1", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2024, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.634995+02	2026-01-11 15:36:55.63501+02	f	1	3	3	21
1466	{"purpose": "Conference", "quarter": "Q2", "total_km": 2000, "travel_type": "Domestic", "co2e_emissions": 510.0, "reporting_year": 2024, "avg_distance_km": 500, "number_of_trips": 2}	2026-01-11 15:36:55.638878+02	2026-01-11 15:36:55.638894+02	f	1	3	3	21
1467	{"purpose": "Administrative", "quarter": "Q2", "total_km": 1600, "travel_type": "Domestic", "co2e_emissions": 408.0, "reporting_year": 2024, "avg_distance_km": 400, "number_of_trips": 2}	2026-01-11 15:36:55.642561+02	2026-01-11 15:36:55.642575+02	f	1	3	3	21
1468	{"purpose": "Conference", "quarter": "Q2", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2024, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.645852+02	2026-01-11 15:36:55.645864+02	f	1	3	3	21
1469	{"purpose": "Research Collaboration", "quarter": "Q2", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2024, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.65069+02	2026-01-11 15:36:55.650707+02	f	1	3	3	21
1470	{"purpose": "Conference", "quarter": "Q2", "total_km": 20000, "travel_type": "International", "co2e_emissions": 3900.0, "reporting_year": 2024, "avg_distance_km": 5000, "number_of_trips": 2}	2026-01-11 15:36:55.656003+02	2026-01-11 15:36:55.656018+02	f	1	3	3	21
1471	{"purpose": "Research Collaboration", "quarter": "Q2", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2024, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.659563+02	2026-01-11 15:36:55.659575+02	f	1	3	3	21
1472	{"purpose": "Training", "quarter": "Q2", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2024, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.66319+02	2026-01-11 15:36:55.663203+02	f	1	3	3	21
1473	{"purpose": "Conference", "quarter": "Q3", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2024, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.66719+02	2026-01-11 15:36:55.667206+02	f	1	3	3	21
1474	{"purpose": "Administrative", "quarter": "Q3", "total_km": 800, "travel_type": "Domestic", "co2e_emissions": 204.0, "reporting_year": 2024, "avg_distance_km": 400, "number_of_trips": 1}	2026-01-11 15:36:55.673867+02	2026-01-11 15:36:55.67388+02	f	1	3	3	21
1475	{"purpose": "Conference", "quarter": "Q3", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2024, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.677693+02	2026-01-11 15:36:55.677704+02	f	1	3	3	21
1476	{"purpose": "Research Collaboration", "quarter": "Q3", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2024, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.681291+02	2026-01-11 15:36:55.681307+02	f	1	3	3	21
1477	{"purpose": "Conference", "quarter": "Q3", "total_km": 10000, "travel_type": "International", "co2e_emissions": 1950.0, "reporting_year": 2024, "avg_distance_km": 5000, "number_of_trips": 1}	2026-01-11 15:36:55.685128+02	2026-01-11 15:36:55.685143+02	f	1	3	3	21
1478	{"purpose": "Research Collaboration", "quarter": "Q3", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2024, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.688866+02	2026-01-11 15:36:55.68888+02	f	1	3	3	21
1479	{"purpose": "Training", "quarter": "Q3", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2024, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.694026+02	2026-01-11 15:36:55.69404+02	f	1	3	3	21
1480	{"purpose": "Conference", "quarter": "Q4", "total_km": 1000, "travel_type": "Domestic", "co2e_emissions": 255.0, "reporting_year": 2024, "avg_distance_km": 500, "number_of_trips": 1}	2026-01-11 15:36:55.69803+02	2026-01-11 15:36:55.698046+02	f	1	3	3	21
1481	{"purpose": "Administrative", "quarter": "Q4", "total_km": 1600, "travel_type": "Domestic", "co2e_emissions": 408.0, "reporting_year": 2024, "avg_distance_km": 400, "number_of_trips": 2}	2026-01-11 15:36:55.701811+02	2026-01-11 15:36:55.701824+02	f	1	3	3	21
1482	{"purpose": "Conference", "quarter": "Q4", "total_km": 3000, "travel_type": "Regional (Middle East)", "co2e_emissions": 675.0, "reporting_year": 2024, "avg_distance_km": 1500, "number_of_trips": 1}	2026-01-11 15:36:55.705139+02	2026-01-11 15:36:55.705152+02	f	1	3	3	21
1483	{"purpose": "Research Collaboration", "quarter": "Q4", "total_km": 4000, "travel_type": "Regional (Middle East)", "co2e_emissions": 900.0, "reporting_year": 2024, "avg_distance_km": 2000, "number_of_trips": 1}	2026-01-11 15:36:55.708509+02	2026-01-11 15:36:55.708523+02	f	1	3	3	21
1484	{"purpose": "Conference", "quarter": "Q4", "total_km": 20000, "travel_type": "International", "co2e_emissions": 3900.0, "reporting_year": 2024, "avg_distance_km": 5000, "number_of_trips": 2}	2026-01-11 15:36:55.715095+02	2026-01-11 15:36:55.71511+02	f	1	3	3	21
1485	{"purpose": "Research Collaboration", "quarter": "Q4", "total_km": 12000, "travel_type": "International", "co2e_emissions": 2340.0, "reporting_year": 2024, "avg_distance_km": 6000, "number_of_trips": 1}	2026-01-11 15:36:55.718813+02	2026-01-11 15:36:55.718825+02	f	1	3	3	21
1486	{"purpose": "Training", "quarter": "Q4", "total_km": 8000, "travel_type": "International", "co2e_emissions": 1560.0, "reporting_year": 2024, "avg_distance_km": 4000, "number_of_trips": 1}	2026-01-11 15:36:55.727091+02	2026-01-11 15:36:55.72711+02	f	1	3	3	21
1487	{"unit": "kg", "category": "Paper Products", "quantity": 27287, "spend_egp": 545740, "co2e_emissions": 25649.78, "reporting_year": 2020, "item_description": "A4 Paper Reams"}	2026-01-11 15:36:55.776366+02	2026-01-11 15:36:55.776382+02	f	1	3	3	22
1488	{"unit": "kg", "category": "Paper Products", "quantity": 541, "spend_egp": 10820, "co2e_emissions": 508.54, "reporting_year": 2020, "item_description": "Envelopes"}	2026-01-11 15:36:55.780121+02	2026-01-11 15:36:55.780135+02	f	1	3	3	22
1489	{"unit": "Units", "category": "Printer Ink/Toner", "quantity": 432, "spend_egp": 64800, "co2e_emissions": 1512.0, "reporting_year": 2020, "item_description": "Laser Toner Cartridges"}	2026-01-11 15:36:55.78396+02	2026-01-11 15:36:55.783973+02	f	1	3	3	22
1490	{"unit": "Units", "category": "Printer Ink/Toner", "quantity": 197, "spend_egp": 98.0, "co2e_emissions": 236.4, "reporting_year": 2020, "item_description": "Inkjet Cartridges"}	2026-01-11 15:36:55.787374+02	2026-01-11 15:36:55.787387+02	f	1	3	3	22
1491	{"unit": "Liters", "category": "Hygiene Supplies", "quantity": 2878, "spend_egp": 86340, "co2e_emissions": 2302.4, "reporting_year": 2020, "item_description": "Soap"}	2026-01-11 15:36:55.792575+02	2026-01-11 15:36:55.79259+02	f	1	3	3	22
1492	{"unit": "Units", "category": "Hygiene Supplies", "quantity": 1470118, "spend_egp": 735059.0, "co2e_emissions": 8820.71, "reporting_year": 2020, "item_description": "Paper Tissues"}	2026-01-11 15:36:55.796241+02	2026-01-11 15:36:55.796254+02	f	1	3	3	22
1493	{"unit": "Liters", "category": "Cleaning Products", "quantity": 1424, "spend_egp": 42720, "co2e_emissions": 712.0, "reporting_year": 2020, "item_description": "Detergents"}	2026-01-11 15:36:55.799851+02	2026-01-11 15:36:55.799864+02	f	1	3	3	22
1494	{"unit": "kg", "category": "Lab Consumables", "quantity": 214, "spend_egp": 4280, "co2e_emissions": 1070.0, "reporting_year": 2020, "item_description": "Chemicals & Reagents"}	2026-01-11 15:36:55.803499+02	2026-01-11 15:36:55.803512+02	f	1	3	3	22
1495	{"unit": "kg", "category": "Paper Products", "quantity": 22413, "spend_egp": 448260, "co2e_emissions": 21068.22, "reporting_year": 2021, "item_description": "A4 Paper Reams"}	2026-01-11 15:36:55.807512+02	2026-01-11 15:36:55.807527+02	f	1	3	3	22
1496	{"unit": "kg", "category": "Paper Products", "quantity": 499, "spend_egp": 9980, "co2e_emissions": 469.06, "reporting_year": 2021, "item_description": "Envelopes"}	2026-01-11 15:36:55.811181+02	2026-01-11 15:36:55.811194+02	f	1	3	3	22
1497	{"unit": "Units", "category": "Printer Ink/Toner", "quantity": 424, "spend_egp": 63600, "co2e_emissions": 1484.0, "reporting_year": 2021, "item_description": "Laser Toner Cartridges"}	2026-01-11 15:36:55.814814+02	2026-01-11 15:36:55.814827+02	f	1	3	3	22
1498	{"unit": "Units", "category": "Printer Ink/Toner", "quantity": 190, "spend_egp": 95.0, "co2e_emissions": 228.0, "reporting_year": 2021, "item_description": "Inkjet Cartridges"}	2026-01-11 15:36:55.818316+02	2026-01-11 15:36:55.818329+02	f	1	3	3	22
1499	{"unit": "Liters", "category": "Hygiene Supplies", "quantity": 2892, "spend_egp": 86760, "co2e_emissions": 2313.6, "reporting_year": 2021, "item_description": "Soap"}	2026-01-11 15:36:55.822303+02	2026-01-11 15:36:55.822319+02	f	1	3	3	22
1500	{"unit": "Units", "category": "Hygiene Supplies", "quantity": 1608475, "spend_egp": 804238.0, "co2e_emissions": 9650.85, "reporting_year": 2021, "item_description": "Paper Tissues"}	2026-01-11 15:36:55.826327+02	2026-01-11 15:36:55.82634+02	f	1	3	3	22
1501	{"unit": "Liters", "category": "Cleaning Products", "quantity": 1531, "spend_egp": 45930, "co2e_emissions": 765.5, "reporting_year": 2021, "item_description": "Detergents"}	2026-01-11 15:36:55.831162+02	2026-01-11 15:36:55.831173+02	f	1	3	3	22
1502	{"unit": "kg", "category": "Lab Consumables", "quantity": 221, "spend_egp": 4420, "co2e_emissions": 1105.0, "reporting_year": 2021, "item_description": "Chemicals & Reagents"}	2026-01-11 15:36:55.835515+02	2026-01-11 15:36:55.835535+02	f	1	3	3	22
1503	{"unit": "kg", "category": "Paper Products", "quantity": 21341, "spend_egp": 426820, "co2e_emissions": 20060.54, "reporting_year": 2022, "item_description": "A4 Paper Reams"}	2026-01-11 15:36:55.839457+02	2026-01-11 15:36:55.839472+02	f	1	3	3	22
1504	{"unit": "kg", "category": "Paper Products", "quantity": 460, "spend_egp": 9200, "co2e_emissions": 432.4, "reporting_year": 2022, "item_description": "Envelopes"}	2026-01-11 15:36:55.843211+02	2026-01-11 15:36:55.843226+02	f	1	3	3	22
1505	{"unit": "Units", "category": "Printer Ink/Toner", "quantity": 392, "spend_egp": 58800, "co2e_emissions": 1372.0, "reporting_year": 2022, "item_description": "Laser Toner Cartridges"}	2026-01-11 15:36:55.846769+02	2026-01-11 15:36:55.846783+02	f	1	3	3	22
1506	{"unit": "Units", "category": "Printer Ink/Toner", "quantity": 190, "spend_egp": 95.0, "co2e_emissions": 228.0, "reporting_year": 2022, "item_description": "Inkjet Cartridges"}	2026-01-11 15:36:55.85052+02	2026-01-11 15:36:55.850533+02	f	1	3	3	22
1507	{"unit": "Liters", "category": "Hygiene Supplies", "quantity": 3326, "spend_egp": 99780, "co2e_emissions": 2660.8, "reporting_year": 2022, "item_description": "Soap"}	2026-01-11 15:36:55.85439+02	2026-01-11 15:36:55.854405+02	f	1	3	3	22
1508	{"unit": "Units", "category": "Hygiene Supplies", "quantity": 1827841, "spend_egp": 913920.0, "co2e_emissions": 10967.05, "reporting_year": 2022, "item_description": "Paper Tissues"}	2026-01-11 15:36:55.8597+02	2026-01-11 15:36:55.859715+02	f	1	3	3	22
1509	{"unit": "Liters", "category": "Cleaning Products", "quantity": 1684, "spend_egp": 50520, "co2e_emissions": 842.0, "reporting_year": 2022, "item_description": "Detergents"}	2026-01-11 15:36:55.863502+02	2026-01-11 15:36:55.863517+02	f	1	3	3	22
1510	{"unit": "kg", "category": "Lab Consumables", "quantity": 216, "spend_egp": 4320, "co2e_emissions": 1080.0, "reporting_year": 2022, "item_description": "Chemicals & Reagents"}	2026-01-11 15:36:55.870613+02	2026-01-11 15:36:55.87063+02	f	1	3	3	22
1511	{"unit": "kg", "category": "Paper Products", "quantity": 21617, "spend_egp": 432340, "co2e_emissions": 20319.98, "reporting_year": 2023, "item_description": "A4 Paper Reams"}	2026-01-11 15:36:55.877314+02	2026-01-11 15:36:55.877328+02	f	1	3	3	22
1512	{"unit": "kg", "category": "Paper Products", "quantity": 452, "spend_egp": 9040, "co2e_emissions": 424.88, "reporting_year": 2023, "item_description": "Envelopes"}	2026-01-11 15:36:55.884302+02	2026-01-11 15:36:55.884319+02	f	1	3	3	22
1513	{"unit": "Units", "category": "Printer Ink/Toner", "quantity": 385, "spend_egp": 57750, "co2e_emissions": 1347.5, "reporting_year": 2023, "item_description": "Laser Toner Cartridges"}	2026-01-11 15:36:55.891233+02	2026-01-11 15:36:55.891248+02	f	1	3	3	22
1514	{"unit": "Units", "category": "Printer Ink/Toner", "quantity": 202, "spend_egp": 101.0, "co2e_emissions": 242.4, "reporting_year": 2023, "item_description": "Inkjet Cartridges"}	2026-01-11 15:36:55.895253+02	2026-01-11 15:36:55.895267+02	f	1	3	3	22
1515	{"unit": "Liters", "category": "Hygiene Supplies", "quantity": 3277, "spend_egp": 98310, "co2e_emissions": 2621.6, "reporting_year": 2023, "item_description": "Soap"}	2026-01-11 15:36:55.899636+02	2026-01-11 15:36:55.899664+02	f	1	3	3	22
1516	{"unit": "Units", "category": "Hygiene Supplies", "quantity": 1652375, "spend_egp": 826188.0, "co2e_emissions": 9914.25, "reporting_year": 2023, "item_description": "Paper Tissues"}	2026-01-11 15:36:55.903616+02	2026-01-11 15:36:55.90363+02	f	1	3	3	22
1517	{"unit": "Liters", "category": "Cleaning Products", "quantity": 1477, "spend_egp": 44310, "co2e_emissions": 738.5, "reporting_year": 2023, "item_description": "Detergents"}	2026-01-11 15:36:55.90732+02	2026-01-11 15:36:55.907334+02	f	1	3	3	22
1518	{"unit": "kg", "category": "Lab Consumables", "quantity": 195, "spend_egp": 3900, "co2e_emissions": 975.0, "reporting_year": 2023, "item_description": "Chemicals & Reagents"}	2026-01-11 15:36:55.911329+02	2026-01-11 15:36:55.911346+02	f	1	3	3	22
1519	{"unit": "kg", "category": "Paper Products", "quantity": 20705, "spend_egp": 414100, "co2e_emissions": 19462.7, "reporting_year": 2024, "item_description": "A4 Paper Reams"}	2026-01-11 15:36:55.915867+02	2026-01-11 15:36:55.915887+02	f	1	3	3	22
1520	{"unit": "kg", "category": "Paper Products", "quantity": 394, "spend_egp": 7880, "co2e_emissions": 370.36, "reporting_year": 2024, "item_description": "Envelopes"}	2026-01-11 15:36:55.919789+02	2026-01-11 15:36:55.919806+02	f	1	3	3	22
1521	{"unit": "Units", "category": "Printer Ink/Toner", "quantity": 425, "spend_egp": 63750, "co2e_emissions": 1487.5, "reporting_year": 2024, "item_description": "Laser Toner Cartridges"}	2026-01-11 15:36:55.923599+02	2026-01-11 15:36:55.923616+02	f	1	3	3	22
1522	{"unit": "Units", "category": "Printer Ink/Toner", "quantity": 229, "spend_egp": 114.0, "co2e_emissions": 274.8, "reporting_year": 2024, "item_description": "Inkjet Cartridges"}	2026-01-11 15:36:55.927387+02	2026-01-11 15:36:55.927402+02	f	1	3	3	22
1523	{"unit": "Liters", "category": "Hygiene Supplies", "quantity": 3158, "spend_egp": 94740, "co2e_emissions": 2526.4, "reporting_year": 2024, "item_description": "Soap"}	2026-01-11 15:36:55.931546+02	2026-01-11 15:36:55.931566+02	f	1	3	3	22
1524	{"unit": "Units", "category": "Hygiene Supplies", "quantity": 1724643, "spend_egp": 862322.0, "co2e_emissions": 10347.86, "reporting_year": 2024, "item_description": "Paper Tissues"}	2026-01-11 15:36:55.937072+02	2026-01-11 15:36:55.93709+02	f	1	3	3	22
1525	{"unit": "Liters", "category": "Cleaning Products", "quantity": 1691, "spend_egp": 50730, "co2e_emissions": 845.5, "reporting_year": 2024, "item_description": "Detergents"}	2026-01-11 15:36:55.949121+02	2026-01-11 15:36:55.949136+02	f	1	3	3	22
1526	{"unit": "kg", "category": "Lab Consumables", "quantity": 210, "spend_egp": 4200, "co2e_emissions": 1050.0, "reporting_year": 2024, "item_description": "Chemicals & Reagents"}	2026-01-11 15:36:55.953319+02	2026-01-11 15:36:55.953336+02	f	1	3	3	22
1527	{"notes": "FY2020 GHG Inventory - Smart Village Campus", "scope_1_total": 285, "scope_2_total": 1420, "scope_3_total": 680, "reporting_year": 2020, "total_emissions": 2385, "reporting_period": "January 1 - December 31, 2020", "intensity_per_sqm": 0.053, "verification_status": "Verified", "intensity_per_student": 0.745}	2026-01-11 15:36:56.022598+02	2026-01-11 15:36:56.022626+02	f	1	3	3	23
1528	{"notes": "FY2021 GHG Inventory - Smart Village Campus", "scope_1_total": 278, "scope_2_total": 1480, "scope_3_total": 520, "reporting_year": 2021, "total_emissions": 2278, "reporting_period": "January 1 - December 31, 2021", "intensity_per_sqm": 0.0506, "verification_status": "Verified", "intensity_per_student": 0.68}	2026-01-11 15:36:56.026748+02	2026-01-11 15:36:56.026762+02	f	1	3	3	23
1529	{"notes": "FY2022 GHG Inventory - Smart Village Campus", "scope_1_total": 290, "scope_2_total": 1550, "scope_3_total": 720, "reporting_year": 2022, "total_emissions": 2560, "reporting_period": "January 1 - December 31, 2022", "intensity_per_sqm": 0.0569, "verification_status": "Verified", "intensity_per_student": 0.731}	2026-01-11 15:36:56.030315+02	2026-01-11 15:36:56.030325+02	f	1	3	3	23
1530	{"notes": "FY2023 GHG Inventory - Smart Village Campus", "scope_1_total": 295, "scope_2_total": 1620, "scope_3_total": 780, "reporting_year": 2023, "total_emissions": 2695, "reporting_period": "January 1 - December 31, 2023", "intensity_per_sqm": 0.0561, "verification_status": "Verified", "intensity_per_student": 0.738}	2026-01-11 15:36:56.033753+02	2026-01-11 15:36:56.033764+02	f	1	3	3	23
1531	{"notes": "Preliminary data, pending Q4 reconciliation", "scope_1_total": 288, "scope_2_total": 1580, "scope_3_total": 810, "reporting_year": 2024, "total_emissions": 2678, "reporting_period": "January 1 - December 31, 2024", "intensity_per_sqm": 0.0558, "verification_status": "Pending Review", "intensity_per_student": 0.705}	2026-01-11 15:36:56.038324+02	2026-01-11 15:36:56.03834+02	f	1	3	3	23
\.


--
-- Data for Name: dataschema_datatable; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.dataschema_datatable (id, title, name, description, version, is_archived, created_at, updated_at, created_by_id, module_id, updated_by_id) FROM stdin;
6	Boilers / Water heaters	boilers_water_heaters	إجمالي الوقود المستهلك في الغلايات او سخانات المياه التي تعمل بالوقود خلال العام\n\nNatural Gas	1	f	2025-08-04 13:43:27.509703+03	2025-08-04 13:43:27.509715+03	\N	5	\N
7	On-site Power Generators	on_site_power_generators	إجمالي الوقود المستهلك في مولدات القوى الكهربائية داخل المنشأة خلال العام\n\n\nNatural Gas\nDiesel\nGasoline	1	f	2025-08-04 13:45:49.334517+03	2025-08-04 13:45:49.334527+03	\N	5	\N
8	Laboratory	laboratory	lab burners and specialized combustion devices\nاستهلاك المعامل من الوقود خلال العام	1	f	2025-08-04 13:51:28.153057+03	2025-08-04 13:51:55.720172+03	\N	5	\N
9	Campus Kitchens / Canteens	campus_kitchens_canteens	إجمالي استهلاك الوقود السنوي في المطاعم/ المطابخ/ الكافيتريات ( المملوكة للمنشأة)\n\n\nNatural Gas\nLPG	1	f	2025-08-04 13:52:57.314013+03	2025-08-04 13:53:23.251159+03	\N	5	\N
10	Diesel Generators	diesel_generators	On-site backup power generators	1	f	2026-01-11 15:36:48.758983+02	2026-01-11 15:36:48.759421+02	3	5	3
11	Natural Gas Boilers	natural_gas_boilers	Water heating systems	1	f	2026-01-11 15:36:48.836242+02	2026-01-11 15:36:48.836258+02	3	5	3
12	Kitchen LPG Usage	kitchen_lpg	Campus kitchen/canteen gas consumption	1	f	2026-01-11 15:36:48.895412+02	2026-01-11 15:36:48.89543+02	3	5	3
13	Fleet Fuel Consumption	fleet_fuel	Fuel consumed by university-owned vehicles	1	f	2026-01-11 15:36:49.526653+02	2026-01-11 15:36:49.526668+02	3	6	3
14	Refrigerant Leakage	refrigerant_leakage	Annual refrigerant losses from HVAC systems	1	f	2026-01-11 15:36:51.116754+02	2026-01-11 15:36:51.116771+02	3	7	3
15	Fire Suppression Systems	fire_suppression	CO2 and other fire suppression gas releases	1	f	2026-01-11 15:36:51.244408+02	2026-01-11 15:36:51.244423+02	3	7	3
16	Purchased Electricity	purchased_electricity	Grid electricity consumption by building	1	f	2026-01-11 15:36:51.298271+02	2026-01-11 15:36:51.298287+02	3	8	3
17	Purchased Cooling	purchased_cooling	District cooling / chilled water consumption	1	f	2026-01-11 15:36:51.347111+02	2026-01-11 15:36:51.347125+02	3	8	3
18	Water Consumption	water_consumption	Municipal water usage and wastewater	1	f	2026-01-11 15:36:52.419211+02	2026-01-11 15:36:52.419227+02	3	13	3
19	Commuting Survey Data	commuting_survey	Annual employee and student commuting patterns	1	f	2026-01-11 15:36:52.730056+02	2026-01-11 15:36:52.73007+02	3	14	3
20	Waste Disposal	waste_disposal	Monthly waste generation by type and disposal method	1	f	2026-01-11 15:36:52.994186+02	2026-01-11 15:36:52.9942+02	3	15	3
21	Air Travel	air_travel	Faculty and staff air travel for conferences, meetings	1	f	2026-01-11 15:36:55.100422+02	2026-01-11 15:36:55.100476+02	3	16	3
22	Office Supplies & Consumables	office_consumables	Paper, ink, hygiene supplies, etc.	1	f	2026-01-11 15:36:55.733363+02	2026-01-11 15:36:55.733378+02	3	9	3
23	Annual GHG Inventory Summary	annual_ghg_summary	Aggregated annual emissions by scope for VVB reporting	1	f	2026-01-11 15:36:55.959889+02	2026-01-11 15:36:55.959906+02	3	8	3
\.


--
-- Data for Name: dataschema_schemachangelog; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.dataschema_schemachangelog (id, action, before, after, "timestamp", notes, data_field_id, data_table_id, user_id) FROM stdin;
\.


--
-- Data for Name: django_admin_log; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.django_admin_log (id, action_time, object_id, object_repr, action_flag, change_message, content_type_id, user_id) FROM stdin;
1	2025-07-08 11:40:23.094818+03	2	AAST Carbon	1	[{"added": {}}]	2	4
2	2025-07-08 11:44:31.418357+03	1	AAST Carbon (AAST Carbon)	1	[{"added": {}}]	5	4
3	2025-07-08 11:44:44.244016+03	1	Energy (AAST Carbon)	1	[{"added": {}}]	6	4
4	2025-07-08 11:44:49.848497+03	2	Water (AAST Carbon)	1	[{"added": {}}]	6	4
5	2025-07-08 11:45:00.467243+03	3	Transportation (AAST Carbon)	1	[{"added": {}}]	6	4
6	2025-07-08 11:45:12.799975+03	4	ABC (AAST Carbon)	1	[{"added": {}}]	6	4
7	2025-07-08 11:46:02.97472+03	1	admins_group	1	[{"added": {}}]	13	4
8	2025-07-08 11:47:23.101634+03	2	dataowners_group	1	[{"added": {}}]	13	4
9	2025-07-08 11:48:14.577839+03	3	auditors_group	1	[{"added": {}}]	13	4
10	2025-07-08 11:52:40.127107+03	6	dataowner1 (AAST Carbon)	1	[{"added": {}}]	3	4
11	2025-07-08 12:01:28.359957+03	7	dataowner2 (AAST Carbon)	1	[{"added": {}}]	3	4
12	2025-07-08 12:01:59.462063+03	8	auditor1 (AAST Carbon)	1	[{"added": {}}]	3	4
13	2025-07-08 12:02:18.797966+03	8	auditor1 (AAST Carbon)	2	[{"changed": {"fields": ["Groups"]}}]	3	4
14	2025-07-08 12:02:42.61768+03	6	dataowner1 (AAST Carbon)	2	[{"changed": {"fields": ["Groups"]}}]	3	4
15	2025-07-08 12:02:49.593289+03	7	dataowner2 (AAST Carbon)	2	[{"changed": {"fields": ["Groups"]}}]	3	4
16	2025-07-08 12:02:56.898071+03	3	admin (Default Tenant)	2	[{"changed": {"fields": ["Groups"]}}]	3	4
17	2025-07-08 12:04:20.845716+03	3	admin (AAST Carbon)	2	[{"changed": {"fields": ["Tenant"]}}]	3	4
18	2025-07-08 12:04:47.409437+03	1	admin (AAST Carbon) as admins_group in AAST Carbon	1	[{"added": {}}]	1	4
19	2025-07-08 12:05:04.1019+03	2	auditor1 (AAST Carbon) as auditors_group in Project:AAST Carbon (AAST Carbon)	1	[{"added": {}}]	1	4
20	2025-07-08 12:05:15.168862+03	3	dataowner1 (AAST Carbon) as dataowners_group in Project:AAST Carbon (AAST Carbon)/Module:Energy (AAST Carbon)	1	[{"added": {}}]	1	4
21	2025-07-08 12:05:29.945199+03	4	dataowner2 (AAST Carbon) as dataowners_group in Project:AAST Carbon (AAST Carbon)/Module:Water (AAST Carbon)	1	[{"added": {}}]	1	4
22	2025-07-08 13:32:18.33152+03	5	admin (AAST Carbon) as admins_group in AAST Carbon	1	[{"added": {}}]	1	4
23	2025-07-08 14:58:49.523069+03	6	ahmed (Default Tenant) as admins_group in AAST Carbon	1	[{"added": {}}]	1	4
24	2025-07-08 14:59:44.47853+03	6	ahmed (Default Tenant) as admins_group in Project:AAST Carbon (AAST Carbon)	2	[{"changed": {"fields": ["Project"]}}]	1	4
25	2025-07-08 15:34:03.768303+03	4	admin	1	[{"added": {}}]	13	4
26	2025-07-08 15:34:21.856221+03	7	ahmed (Default Tenant) as admin in Project:AAST Carbon (AAST Carbon)	1	[{"added": {}}]	1	4
27	2025-07-08 15:40:14.759609+03	4	ahmed (Default Tenant)	2	[]	3	4
28	2025-07-08 15:42:18.162364+03	3	admin (AAST Carbon)	2	[{"changed": {"fields": ["Groups"]}}]	3	4
29	2025-07-08 15:42:51.819379+03	4	ahmed (Default Tenant)	2	[{"changed": {"fields": ["Groups"]}}]	3	4
30	2025-07-08 15:43:39.492663+03	4	ahmed (AAST Carbon)	2	[{"changed": {"fields": ["Groups", "Tenant"]}}]	3	4
31	2025-07-08 15:44:38.040325+03	7	ahmed (AAST Carbon) as admin in Project:AAST Carbon (AAST Carbon)	3		1	4
32	2025-07-09 10:08:38.554384+03	2	aaa (AAST Carbon)	1	[{"added": {}}]	5	4
33	2025-07-09 10:09:17.239896+03	8	ahmed (AAST Carbon) as admin in Project:aaa (AAST Carbon)	1	[{"added": {}}]	1	4
34	2025-07-09 10:34:02.325615+03	6	dataowner1 (AAST Carbon)	2	[{"changed": {"fields": ["Groups"]}}]	3	4
35	2025-07-09 10:34:23.922136+03	3	dataowner1 (AAST Carbon) as dataowners_group in Project:AAST Carbon (AAST Carbon)/Module:Energy (AAST Carbon)	2	[]	1	4
36	2025-07-09 14:11:56.800153+03	1	aaa (ABC (AAST Carbon))	1	[{"added": {}}, {"added": {"name": "data field", "object": "aa (string) in aaa"}}]	7	4
37	2025-07-09 14:31:59.074517+03	2	aaa (AAST Carbon)	3		5	4
38	2025-07-13 13:11:25.037204+03	9	dataowner1 (AAST Carbon) as dataowners_group in Project:AAST Carbon (AAST Carbon)/Module:Water (AAST Carbon)	1	[{"added": {}}]	1	4
39	2025-07-13 14:06:48.984827+03	9	admin1 (AAST Carbon)	1	[{"added": {}}]	3	4
40	2025-07-13 14:07:01.450062+03	9	admin1 (AAST Carbon)	2	[{"changed": {"fields": ["Groups"]}}]	3	4
41	2025-07-13 14:07:41.995882+03	10	admin1 (AAST Carbon) as admins_group in Project:AAST Carbon (AAST Carbon)	1	[{"added": {}}]	1	4
42	2025-07-20 10:19:48.264499+03	1	Energy (AAST Carbon)	2	[]	6	4
43	2025-08-04 09:38:36.342262+03	4	ahmed (AAST Carbon)	2	[{"changed": {"fields": ["password"]}}]	3	4
44	2025-08-04 10:00:49.075337+03	1	Energy (AAST Carbon) - Scope 1	2	[]	6	4
45	2025-08-04 10:01:23.046736+03	3	Transportation (AAST Carbon) - Scope 2	2	[{"changed": {"fields": ["Scope"]}}]	6	4
46	2025-08-04 10:01:27.555492+03	2	Water (AAST Carbon) - Scope 2	2	[{"changed": {"fields": ["Scope"]}}]	6	4
47	2025-08-04 13:38:24.31495+03	5	Stationary Combustion (AAST Carbon) - Scope 1	1	[{"added": {}}]	6	4
48	2025-08-04 13:38:37.608145+03	6	Mobile Combustion (AAST Carbon) - Scope 1	1	[{"added": {}}]	6	4
49	2025-08-04 13:38:46.574939+03	7	Fugitive Emissions (AAST Carbon) - Scope 1	1	[{"added": {}}]	6	4
50	2025-08-04 13:39:02.259591+03	4	ABC (AAST Carbon) - Scope 1	3		6	4
51	2025-08-04 13:39:02.25964+03	3	Transportation (AAST Carbon) - Scope 2	3		6	4
52	2025-08-04 13:39:02.25966+03	2	Water (AAST Carbon) - Scope 2	3		6	4
53	2025-08-04 13:39:02.259675+03	1	Energy (AAST Carbon) - Scope 1	3		6	4
54	2025-08-04 13:39:44.16446+03	8	Purchased Energy (AAST Carbon) - Scope 2	1	[{"added": {}}]	6	4
55	2025-08-04 13:39:54.023626+03	9	Consumable Purchased goods and services (AAST Carbon) - Scope 2	1	[{"added": {}}]	6	4
56	2025-08-04 13:40:01.134846+03	10	Capital Goods (AAST Carbon) - Scope 2	1	[{"added": {}}]	6	4
57	2025-08-04 13:40:08.561606+03	11	Fertilizers (AAST Carbon) - Scope 2	1	[{"added": {}}]	6	4
58	2025-08-04 13:40:35.616528+03	12	Fuel & Energy Related Emissions (AAST Carbon) - Scope 3	1	[{"added": {}}]	6	4
59	2025-08-04 13:40:53.870202+03	9	Consumable Purchased goods and services (AAST Carbon) - Scope 3	2	[{"changed": {"fields": ["Scope"]}}]	6	4
60	2025-08-04 13:41:02.395524+03	10	Capital Goods (AAST Carbon) - Scope 3	2	[{"changed": {"fields": ["Scope"]}}]	6	4
61	2025-08-04 13:41:08.273489+03	11	Fertilizers (AAST Carbon) - Scope 3	2	[{"changed": {"fields": ["Scope"]}}]	6	4
62	2025-08-04 13:41:16.020874+03	12	Fuel & Energy Related Emissions (AAST Carbon) - Scope 3	2	[]	6	4
63	2025-08-04 13:41:23.831953+03	13	Water Usage/Waste (AAST Carbon) - Scope 3	1	[{"added": {}}]	6	4
64	2025-08-04 13:41:30.842175+03	14	Annual Commuting (AAST Carbon) - Scope 3	1	[{"added": {}}]	6	4
65	2025-08-04 13:41:40.716199+03	15	Waste (AAST Carbon) - Scope 3	1	[{"added": {}}]	6	4
66	2025-08-04 13:41:47.310851+03	16	Business travel (AAST Carbon) - Scope 3	1	[{"added": {}}]	6	4
67	2025-08-04 13:41:54.142893+03	17	Upstream transportation and distribution Purchased Goods (AAST Carbon) - Scope 3	1	[{"added": {}}]	6	4
68	2025-08-04 13:42:01.443236+03	18	Upstream Leased Assets (AAST Carbon) - Scope 3	1	[{"added": {}}]	6	4
\.


--
-- Data for Name: django_content_type; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.django_content_type (id, app_label, model) FROM stdin;
1	accounts	scopedrole
2	accounts	tenant
3	accounts	user
4	accounts	roleassignmentauditlog
5	core	project
6	core	module
7	dataschema	datatable
8	dataschema	datarow
9	dataschema	datafield
10	dataschema	schemachangelog
11	admin	logentry
12	auth	permission
13	auth	group
14	contenttypes	contenttype
15	sessions	session
16	core	feedback
17	token_blacklist	blacklistedtoken
18	token_blacklist	outstandingtoken
19	ai_copilot	useraipreference
20	ai_copilot	proactiveinsight
21	ai_copilot	conversationmessage
\.


--
-- Data for Name: django_migrations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.django_migrations (id, app, name, applied) FROM stdin;
1	contenttypes	0001_initial	2025-07-08 11:27:29.086118+03
2	contenttypes	0002_remove_content_type_name	2025-07-08 11:27:29.098451+03
3	auth	0001_initial	2025-07-08 11:27:29.172892+03
4	auth	0002_alter_permission_name_max_length	2025-07-08 11:27:29.177576+03
5	auth	0003_alter_user_email_max_length	2025-07-08 11:27:29.182184+03
6	auth	0004_alter_user_username_opts	2025-07-08 11:27:29.18733+03
7	auth	0005_alter_user_last_login_null	2025-07-08 11:27:29.191763+03
8	auth	0006_require_contenttypes_0002	2025-07-08 11:27:29.193762+03
9	auth	0007_alter_validators_add_error_messages	2025-07-08 11:27:29.199305+03
10	auth	0008_alter_user_username_max_length	2025-07-08 11:27:29.203775+03
11	auth	0009_alter_user_last_name_max_length	2025-07-08 11:27:29.208046+03
12	auth	0010_alter_group_name_max_length	2025-07-08 11:27:29.215486+03
13	auth	0011_update_proxy_permissions	2025-07-08 11:27:29.221089+03
14	auth	0012_alter_user_first_name_max_length	2025-07-08 11:27:29.225912+03
15	accounts	0001_initial	2025-07-08 11:27:29.319299+03
16	core	0001_initial	2025-07-08 11:27:29.350691+03
17	accounts	0002_initial	2025-07-08 11:27:29.462553+03
18	admin	0001_initial	2025-07-08 11:27:29.490329+03
19	admin	0002_logentry_remove_auto_add	2025-07-08 11:27:29.497464+03
20	admin	0003_logentry_add_action_flag_choices	2025-07-08 11:27:29.505353+03
21	dataschema	0001_initial	2025-07-08 11:27:29.648974+03
22	sessions	0001_initial	2025-07-08 11:27:29.668089+03
23	accounts	0003_alter_user_tenant	2025-07-08 11:29:00.873907+03
24	core	0002_feedback	2025-07-13 14:53:51.854193+03
25	core	0003_module_scope	2025-08-04 10:00:34.943616+03
26	accounts	0004_alter_user_tenant	2026-01-11 14:54:11.526574+02
27	token_blacklist	0001_initial	2026-01-11 14:54:11.627106+02
28	token_blacklist	0002_outstandingtoken_jti_hex	2026-01-11 14:54:11.642429+02
29	token_blacklist	0003_auto_20171017_2007	2026-01-11 14:54:11.659792+02
30	token_blacklist	0004_auto_20171017_2013	2026-01-11 14:54:11.684245+02
31	token_blacklist	0005_remove_outstandingtoken_jti	2026-01-11 14:54:11.700437+02
32	token_blacklist	0006_auto_20171017_2113	2026-01-11 14:54:11.716427+02
33	token_blacklist	0007_auto_20171017_2214	2026-01-11 14:54:11.748002+02
34	token_blacklist	0008_migrate_to_bigautofield	2026-01-11 14:54:11.827331+02
35	token_blacklist	0010_fix_migrate_to_bigautofield	2026-01-11 14:54:11.845944+02
36	token_blacklist	0011_linearizes_history	2026-01-11 14:54:11.849334+02
37	token_blacklist	0012_alter_outstandingtoken_user	2026-01-11 14:54:11.886594+02
38	ai_copilot	0001_initial	2026-01-12 13:02:18.397464+02
\.


--
-- Data for Name: django_session; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.django_session (session_key, session_data, expire_date) FROM stdin;
mwibb8lg5a5jmme8sawu9kyc7e0nsisg	.eJxVjEsOwjAMBe-SNYoSN40bluw5Q2THLimgVupnhbg7VOoCtm9m3stk2taat0XnPIg5m2BOvxtTeei4A7nTeJtsmcZ1Htjuij3oYq-T6PNyuH8HlZb6rZXVeWQgctymvmEQLKC97xtJEBGTjxhaSlFi24EnCA5Do5gQhDtn3h_rYDdK:1uZ3ry:a2kGEerX-k8wC_UM4QvLr68USt5yrtPP9sCYVynM_cw	2025-07-22 11:40:06.777481+03
e5ng6bzmm1bvc9tc3qvxj4asf6kv2j5g	.eJxVjEEOwiAQRe_C2hCgDJ26dO8ZCMyAVA0kpV0Z765NutDtf-_9l_BhW4vfelr8zOIsrDj9bjHQI9Ud8D3UW5PU6rrMUe6KPGiX18bpeTncv4MSevnW6AYL2VjDzGoghTYljSoH4hi0w8iGtdJjBnAEBrIbDQLSgAR6mrR4fwDctDdH:1ud2tM:jDnVDT3_batR7z5df8nDDeLfUiJ3_vr0JjkQYofH3dM	2025-08-02 11:26:00.152117+03
iqob69b65x8h9zvk5z9rnnn2pkom1hya	.eJxVzMEOwiAQBNB_4WwI4LZdPHr3Gwgsi1QNJKU9Gf9dmvSg13kz8xbOb2t2W-PFzVFcBIjTbxY8PbnsEB--3KukWtZlDnKvyEObvNXIr-vR_TvIvuW-Hr0yJjIxwWRZny0kGzgisQEF0A0mBK20StBNJ9B24MGOFAARk_h8Ad-MN1k:1uioqC:ovQK6feFhUZ35kwvMkeAGMNQ1F87t7FPEM9K-vKCj4o	2025-08-18 09:38:36.353373+03
7mdwykk92ne5l6hp0kc1nxrm3qp48eh8	.eJxVzMEOwiAQBNB_4WwI4LZdPHr3Gwgsi1QNJKU9Gf9dmvSg13kz8xbOb2t2W-PFzVFcBIjTbxY8PbnsEB--3KukWtZlDnKvyEObvNXIr-vR_TvIvuW-Hr0yJjIxwWRZny0kGzgisQEF0A0mBK20StBNJ9B24MGOFAARk_h8Ad-MN1k:1uitml:cgRJLo764VVYF15-kUpf7-EFe8FcBlh4vik8Fw8VFVc	2025-08-18 14:55:23.921923+03
\.


--
-- Data for Name: token_blacklist_blacklistedtoken; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.token_blacklist_blacklistedtoken (id, blacklisted_at, token_id) FROM stdin;
1	2026-01-11 15:19:58.0417+02	1
2	2026-01-11 15:38:57.057295+02	3
3	2026-01-11 15:42:10.210083+02	4
4	2026-01-11 15:45:36.739004+02	5
5	2026-01-11 16:00:06.379397+02	6
6	2026-01-11 16:23:37.321328+02	7
10	2026-01-11 16:39:10.882019+02	9
13	2026-01-12 11:32:33.410965+02	18
14	2026-01-12 11:50:24.132686+02	19
\.


--
-- Data for Name: token_blacklist_outstandingtoken; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.token_blacklist_outstandingtoken (id, token, created_at, expires_at, user_id, jti) FROM stdin;
1	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODIyMDcyNCwiaWF0IjoxNzY4MTM0MzI0LCJqdGkiOiI4OTI4YzRiNDczYWM0MzYzODhkOWM2NzlhMGVkOGJlNyIsInVzZXJfaWQiOjN9.txkWIG2SmLmsBs5GvwQbmQMvsuEr_f4MqZ8oNYTrvnA	2026-01-11 15:19:57.906877+02	2026-01-12 14:25:24+02	3	8928c4b473ac436388d9c679a0ed8be7
2	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0MjM5NywiaWF0IjoxNzY4MTM3NTk3LCJqdGkiOiI4Y2UzMDNmNTMxMTE0NzJhYjliOGRhZjJlNDBhODBkZSIsInVzZXJfaWQiOjN9.lACs5SB9ebpdBrhZe5YcDt0JqUDSOznA0_GRkjQKf-I	2026-01-11 15:19:57.906877+02	2026-01-18 15:19:57+02	3	8ce303f53111472ab9b8daf2e40a80de
3	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0MjQxOCwiaWF0IjoxNzY4MTM3NjE4LCJqdGkiOiJlNmUzMTg2NTg0ZDQ0MzA5Yjg5MzRhNmRhODJmYjdhMSIsInVzZXJfaWQiOjN9.-wNcXtkjIva0T-T1M5x_9AHF5iqxX0KkFUSLsbU6IJ8	2026-01-11 15:20:18.845083+02	2026-01-18 15:20:18+02	3	e6e3186584d44309b8934a6da82fb7a1
4	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0MzUzNiwiaWF0IjoxNzY4MTM4NzM2LCJqdGkiOiJlYWZkY2JmODY2NDQ0OGYxOTgwMzYwOWQwODA5NzkyZSIsInVzZXJfaWQiOjN9.uY9kHmcdz0HgJU3hCSGZ5Du4DAMFm5WOid6V1bgRhXo	2026-01-11 15:38:56.790969+02	2026-01-18 15:38:56+02	3	eafdcbf8664448f19803609d0809792e
5	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0Mzc0OCwiaWF0IjoxNzY4MTM4OTQ4LCJqdGkiOiJkZWE0YTMzOGUyYWI0YTBjYWU1MTg2M2ExN2U5NjVkZiIsInVzZXJfaWQiOjN9.3DkzdtIMvaFoX8VuMX7G3uREXx-dRucXe4agFErxrb4	2026-01-11 15:42:28.911033+02	2026-01-18 15:42:28+02	3	dea4a338e2ab4a0cae51863a17e965df
6	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0Mzk0MiwiaWF0IjoxNzY4MTM5MTQyLCJqdGkiOiJlOWRmMTlkMTZiMDU0ZmIwYWViMTZjM2VlNGQ1MDAxYiIsInVzZXJfaWQiOjN9.urqtUZiqjw9EjkBFZum7di-W-L3ZhOnllWwFhO_e-SI	2026-01-11 15:45:42.762421+02	2026-01-18 15:45:42+02	3	e9df19d16b054fb0aeb16c3ee4d5001b
7	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0NDgwNiwiaWF0IjoxNzY4MTQwMDA2LCJqdGkiOiJjNjM0NGU0YTFjNTM0OWY1ODU2ZWM0MTk2NzE1MWJmNSIsInVzZXJfaWQiOjN9.CwXCNPLPl91eZx_PTGun-yqCruNwPJbdk2Vc0_UH58I	2026-01-11 16:00:06.291182+02	2026-01-18 16:00:06+02	3	c6344e4a1c5349f5856ec41967151bf5
8	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0NjIxNywiaWF0IjoxNzY4MTQxNDE3LCJqdGkiOiJkOGU4NTE4ODhkMjA0ZmU5YjU2NjM2NGMzYjIyMDM4ZSIsInVzZXJfaWQiOjN9.gE3_1prFcCUDxzUxYDljrFTPXH2QpJh-0h7_yj0tkl0	2026-01-11 16:23:37.202583+02	2026-01-18 16:23:37+02	3	d8e851888d204fe9b566364c3b22038e
9	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0NjIyNSwiaWF0IjoxNzY4MTQxNDI1LCJqdGkiOiI4OGVmM2MyYmM2NjY0ZjE2YjM0NTkwZGEzZDk4NTlhMCIsInVzZXJfaWQiOjN9.biOzjhMw510LlMbjNBklHaVTCxknuvtQ5bh3sBkg91g	2026-01-11 16:23:45.255299+02	2026-01-18 16:23:45+02	3	88ef3c2bc6664f16b34590da3d9859a0
10	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0NzE1MCwiaWF0IjoxNzY4MTQyMzUwLCJqdGkiOiIyNjAzYjAzZTNkZjI0ZWYyYjk5Mjc4ZmVlN2Y1YjY5OCIsInVzZXJfaWQiOjN9.xBF3Etz0ckZTGsRHuM6uD2AGdlzSyKz_WMEweMSCFb8	2026-01-11 16:39:10.785079+02	2026-01-18 16:39:10+02	3	2603b03e3df24ef2b99278fee7f5b698
11	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0NzE1MCwiaWF0IjoxNzY4MTQyMzUwLCJqdGkiOiJjZTBhNzEzMzdiMjA0YzlmOTg3NTFhMTM3ZjE5NGQxMSIsInVzZXJfaWQiOjN9.sAEgiH3IE8ghfW3qBnxCOal2UDBhdZl7Qrkz60fWVN4	2026-01-11 16:39:10.785966+02	2026-01-18 16:39:10+02	3	ce0a71337b204c9f98751a137f194d11
12	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0NzE1MCwiaWF0IjoxNzY4MTQyMzUwLCJqdGkiOiJkM2E0OGQ3YWU1NzI0MzcyYjhlNTJlM2RkYWRjNDg1YiIsInVzZXJfaWQiOjN9.L8h68joomT2vqt3rGOaqM63vnQ3wdBB5qPDEqqmzXnw	2026-01-11 16:39:10.778491+02	2026-01-18 16:39:10+02	3	d3a48d7ae5724372b8e52e3ddadc485b
13	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0NzE1MCwiaWF0IjoxNzY4MTQyMzUwLCJqdGkiOiIwZmJlMzU5YjU4ZTE0MWE5YTljMzcxMjM5Mzg0OGI2ZCIsInVzZXJfaWQiOjN9.fSKVZxYkPAgVKfjW879cSznQ9caPlEtnrz2HPFlXKSA	2026-01-11 16:39:10.782758+02	2026-01-18 16:39:10+02	3	0fbe359b58e141a9a9c3712393848b6d
14	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0NzE1MCwiaWF0IjoxNzY4MTQyMzUwLCJqdGkiOiJkNGQ4YzQwMjI1MzU0NzQwOTRlMTYzYmVlOWUzYWI2NCIsInVzZXJfaWQiOjN9.j2n4KgPJOEajh1IU17T61ea6x4DltX8OfWrSK5zemD8	2026-01-11 16:39:10.784149+02	2026-01-18 16:39:10+02	3	d4d8c4022535474094e163bee9e3ab64
15	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0NzE1MCwiaWF0IjoxNzY4MTQyMzUwLCJqdGkiOiJjMzc1NWU2Mzg0NmY0ODNiYmY3YjlkMjBjNDMxNWMyMyIsInVzZXJfaWQiOjN9.2lktNZhTUPL1nUVK_Qw1qFRnm5wvktX_NyKkz3JoxII	2026-01-11 16:39:10.786769+02	2026-01-18 16:39:10+02	3	c3755e63846f483bbf7b9d20c4315c23
16	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODc0NzE2MCwiaWF0IjoxNzY4MTQyMzYwLCJqdGkiOiIxYWIwNmIwOWMwNmE0ODVjOGFkNDIxZWI0NjhiYzA2OSIsInVzZXJfaWQiOjN9.81wO2z9qvrMcXK6YdbsgvWbCAwFtt2ia7Noy1oYZK5U	2026-01-11 16:39:20.811622+02	2026-01-18 16:39:20+02	3	1ab06b09c06a485c8ad421eb468bc069
17	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODgxNDQ4MCwiaWF0IjoxNzY4MjA5NjgwLCJqdGkiOiIwMzNkYmE3MzI4NzI0NjI5YjI5ODI2YjdiNzg4YTMwZCIsInVzZXJfaWQiOjN9.Qow1-0XQZc2Pelnsr7fWskB04raUsRZsepgykF0l6kY	2026-01-12 11:21:20.093279+02	2026-01-19 11:21:20+02	3	033dba7328724629b29826b7b788a30d
18	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODgxNDkzMSwiaWF0IjoxNzY4MjEwMTMxLCJqdGkiOiIwZGNjYmYxMmU5OTY0OTcyYjAyMmRhNWZjMzZiNTc5ZCIsInVzZXJfaWQiOjN9.H0DMgjdTluYVGrqE3MD7X87sdjtGVWFM9lqnloRmY_A	2026-01-12 11:28:51.884738+02	2026-01-19 11:28:51+02	3	0dccbf12e9964972b022da5fc36b579d
19	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODgxNTE1OSwiaWF0IjoxNzY4MjEwMzU5LCJqdGkiOiJlNWMxMjIxYmNmNTg0ODE2YjBkYzgzMzljMDFjMWFmMiIsInVzZXJfaWQiOjN9.HNtqwH5P7NqfF2nte5wqKOJRxsGms3xk_6T22oWeIsw	2026-01-12 11:32:39.071671+02	2026-01-19 11:32:39+02	3	e5c1221bcf584816b0dc8339c01c1af2
20	eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2ODgxNjIyNCwiaWF0IjoxNzY4MjExNDI0LCJqdGkiOiI0YTA3ZDBiM2Q3MjY0NjhhOTI2ZDBkNGQ0NTE4YTMxMiIsInVzZXJfaWQiOjN9.assPJ935rev8O6MKs31YDzswR3MxdabteDFsumm1gQ4	2026-01-12 11:50:24.123229+02	2026-01-19 11:50:24+02	3	4a07d0b3d726468a926d0d4d4518a312
\.


--
-- Name: accounts_roleassignmentauditlog_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.accounts_roleassignmentauditlog_id_seq', 1, false);


--
-- Name: accounts_scopedrole_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.accounts_scopedrole_id_seq', 18, true);


--
-- Name: accounts_tenant_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.accounts_tenant_id_seq', 4, true);


--
-- Name: accounts_user_groups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.accounts_user_groups_id_seq', 8, true);


--
-- Name: accounts_user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.accounts_user_id_seq', 10, true);


--
-- Name: accounts_user_user_permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.accounts_user_user_permissions_id_seq', 1, false);


--
-- Name: ai_copilot_conversationmessage_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.ai_copilot_conversationmessage_id_seq', 1, false);


--
-- Name: ai_copilot_proactiveinsight_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.ai_copilot_proactiveinsight_id_seq', 1, false);


--
-- Name: ai_copilot_useraipreference_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.ai_copilot_useraipreference_id_seq', 1, false);


--
-- Name: auth_group_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.auth_group_id_seq', 5, true);


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.auth_group_permissions_id_seq', 132, true);


--
-- Name: auth_permission_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.auth_permission_id_seq', 84, true);


--
-- Name: core_feedback_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.core_feedback_id_seq', 2, true);


--
-- Name: core_module_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.core_module_id_seq', 18, true);


--
-- Name: core_project_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.core_project_id_seq', 2, true);


--
-- Name: dataschema_datafield_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.dataschema_datafield_id_seq', 119, true);


--
-- Name: dataschema_datarow_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.dataschema_datarow_id_seq', 1531, true);


--
-- Name: dataschema_datatable_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.dataschema_datatable_id_seq', 23, true);


--
-- Name: dataschema_schemachangelog_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.dataschema_schemachangelog_id_seq', 1, false);


--
-- Name: django_admin_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.django_admin_log_id_seq', 68, true);


--
-- Name: django_content_type_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.django_content_type_id_seq', 21, true);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.django_migrations_id_seq', 38, true);


--
-- Name: token_blacklist_blacklistedtoken_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.token_blacklist_blacklistedtoken_id_seq', 14, true);


--
-- Name: token_blacklist_outstandingtoken_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.token_blacklist_outstandingtoken_id_seq', 20, true);


--
-- Name: accounts_roleassignmentauditlog accounts_roleassignmentauditlog_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_roleassignmentauditlog
    ADD CONSTRAINT accounts_roleassignmentauditlog_pkey PRIMARY KEY (id);


--
-- Name: accounts_scopedrole accounts_scopedrole_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_scopedrole
    ADD CONSTRAINT accounts_scopedrole_pkey PRIMARY KEY (id);


--
-- Name: accounts_scopedrole accounts_scopedrole_user_id_group_id_tenant__c33c3cd9_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_scopedrole
    ADD CONSTRAINT accounts_scopedrole_user_id_group_id_tenant__c33c3cd9_uniq UNIQUE (user_id, group_id, tenant_id, project_id, module_id);


--
-- Name: accounts_tenant accounts_tenant_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_tenant
    ADD CONSTRAINT accounts_tenant_name_key UNIQUE (name);


--
-- Name: accounts_tenant accounts_tenant_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_tenant
    ADD CONSTRAINT accounts_tenant_pkey PRIMARY KEY (id);


--
-- Name: accounts_user_groups accounts_user_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_user_groups
    ADD CONSTRAINT accounts_user_groups_pkey PRIMARY KEY (id);


--
-- Name: accounts_user_groups accounts_user_groups_user_id_group_id_59c0b32f_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_user_groups
    ADD CONSTRAINT accounts_user_groups_user_id_group_id_59c0b32f_uniq UNIQUE (user_id, group_id);


--
-- Name: accounts_user accounts_user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_user
    ADD CONSTRAINT accounts_user_pkey PRIMARY KEY (id);


--
-- Name: accounts_user_user_permissions accounts_user_user_permi_user_id_permission_id_2ab516c2_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_user_user_permissions
    ADD CONSTRAINT accounts_user_user_permi_user_id_permission_id_2ab516c2_uniq UNIQUE (user_id, permission_id);


--
-- Name: accounts_user_user_permissions accounts_user_user_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_user_user_permissions
    ADD CONSTRAINT accounts_user_user_permissions_pkey PRIMARY KEY (id);


--
-- Name: accounts_user accounts_user_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_user
    ADD CONSTRAINT accounts_user_username_key UNIQUE (username);


--
-- Name: ai_copilot_conversationmessage ai_copilot_conversationmessage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_copilot_conversationmessage
    ADD CONSTRAINT ai_copilot_conversationmessage_pkey PRIMARY KEY (id);


--
-- Name: ai_copilot_proactiveinsight ai_copilot_proactiveinsight_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_copilot_proactiveinsight
    ADD CONSTRAINT ai_copilot_proactiveinsight_pkey PRIMARY KEY (id);


--
-- Name: ai_copilot_useraipreference ai_copilot_useraipreference_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_copilot_useraipreference
    ADD CONSTRAINT ai_copilot_useraipreference_pkey PRIMARY KEY (id);


--
-- Name: ai_copilot_useraipreference ai_copilot_useraipreference_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_copilot_useraipreference
    ADD CONSTRAINT ai_copilot_useraipreference_user_id_key UNIQUE (user_id);


--
-- Name: auth_group auth_group_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_name_key UNIQUE (name);


--
-- Name: auth_group_permissions auth_group_permissions_group_id_permission_id_0cd325b0_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_permission_id_0cd325b0_uniq UNIQUE (group_id, permission_id);


--
-- Name: auth_group_permissions auth_group_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_group auth_group_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_pkey PRIMARY KEY (id);


--
-- Name: auth_permission auth_permission_content_type_id_codename_01ab375a_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_codename_01ab375a_uniq UNIQUE (content_type_id, codename);


--
-- Name: auth_permission auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- Name: core_feedback core_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.core_feedback
    ADD CONSTRAINT core_feedback_pkey PRIMARY KEY (id);


--
-- Name: core_module core_module_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.core_module
    ADD CONSTRAINT core_module_pkey PRIMARY KEY (id);


--
-- Name: core_module core_module_project_id_name_66ce4d0c_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.core_module
    ADD CONSTRAINT core_module_project_id_name_66ce4d0c_uniq UNIQUE (project_id, name);


--
-- Name: core_project core_project_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.core_project
    ADD CONSTRAINT core_project_pkey PRIMARY KEY (id);


--
-- Name: core_project core_project_tenant_id_name_566c090f_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.core_project
    ADD CONSTRAINT core_project_tenant_id_name_566c090f_uniq UNIQUE (tenant_id, name);


--
-- Name: dataschema_datafield dataschema_datafield_data_table_id_name_5996a3bc_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datafield
    ADD CONSTRAINT dataschema_datafield_data_table_id_name_5996a3bc_uniq UNIQUE (data_table_id, name);


--
-- Name: dataschema_datafield dataschema_datafield_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datafield
    ADD CONSTRAINT dataschema_datafield_pkey PRIMARY KEY (id);


--
-- Name: dataschema_datarow dataschema_datarow_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datarow
    ADD CONSTRAINT dataschema_datarow_pkey PRIMARY KEY (id);


--
-- Name: dataschema_datatable dataschema_datatable_module_id_name_0414ec63_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datatable
    ADD CONSTRAINT dataschema_datatable_module_id_name_0414ec63_uniq UNIQUE (module_id, name);


--
-- Name: dataschema_datatable dataschema_datatable_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datatable
    ADD CONSTRAINT dataschema_datatable_pkey PRIMARY KEY (id);


--
-- Name: dataschema_schemachangelog dataschema_schemachangelog_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_schemachangelog
    ADD CONSTRAINT dataschema_schemachangelog_pkey PRIMARY KEY (id);


--
-- Name: django_admin_log django_admin_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_pkey PRIMARY KEY (id);


--
-- Name: django_content_type django_content_type_app_label_model_76bd3d3b_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_app_label_model_76bd3d3b_uniq UNIQUE (app_label, model);


--
-- Name: django_content_type django_content_type_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);


--
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- Name: django_session django_session_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_session
    ADD CONSTRAINT django_session_pkey PRIMARY KEY (session_key);


--
-- Name: token_blacklist_blacklistedtoken token_blacklist_blacklistedtoken_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_blacklist_blacklistedtoken
    ADD CONSTRAINT token_blacklist_blacklistedtoken_pkey PRIMARY KEY (id);


--
-- Name: token_blacklist_blacklistedtoken token_blacklist_blacklistedtoken_token_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_blacklist_blacklistedtoken
    ADD CONSTRAINT token_blacklist_blacklistedtoken_token_id_key UNIQUE (token_id);


--
-- Name: token_blacklist_outstandingtoken token_blacklist_outstandingtoken_jti_hex_d9bdf6f7_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_blacklist_outstandingtoken
    ADD CONSTRAINT token_blacklist_outstandingtoken_jti_hex_d9bdf6f7_uniq UNIQUE (jti);


--
-- Name: token_blacklist_outstandingtoken token_blacklist_outstandingtoken_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_blacklist_outstandingtoken
    ADD CONSTRAINT token_blacklist_outstandingtoken_pkey PRIMARY KEY (id);


--
-- Name: accounts_roleassignmentauditlog_actor_id_8dc20397; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_roleassignmentauditlog_actor_id_8dc20397 ON public.accounts_roleassignmentauditlog USING btree (actor_id);


--
-- Name: accounts_roleassignmentauditlog_group_id_0f6b152e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_roleassignmentauditlog_group_id_0f6b152e ON public.accounts_roleassignmentauditlog USING btree (group_id);


--
-- Name: accounts_roleassignmentauditlog_module_id_584e05ea; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_roleassignmentauditlog_module_id_584e05ea ON public.accounts_roleassignmentauditlog USING btree (module_id);


--
-- Name: accounts_roleassignmentauditlog_project_id_cb535b5f; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_roleassignmentauditlog_project_id_cb535b5f ON public.accounts_roleassignmentauditlog USING btree (project_id);


--
-- Name: accounts_roleassignmentauditlog_tenant_id_54dff115; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_roleassignmentauditlog_tenant_id_54dff115 ON public.accounts_roleassignmentauditlog USING btree (tenant_id);


--
-- Name: accounts_roleassignmentauditlog_user_id_e2fac962; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_roleassignmentauditlog_user_id_e2fac962 ON public.accounts_roleassignmentauditlog USING btree (user_id);


--
-- Name: accounts_scopedrole_group_id_cf584c29; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_scopedrole_group_id_cf584c29 ON public.accounts_scopedrole USING btree (group_id);


--
-- Name: accounts_scopedrole_module_id_8b78908b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_scopedrole_module_id_8b78908b ON public.accounts_scopedrole USING btree (module_id);


--
-- Name: accounts_scopedrole_project_id_c1692ed0; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_scopedrole_project_id_c1692ed0 ON public.accounts_scopedrole USING btree (project_id);


--
-- Name: accounts_scopedrole_tenant_id_1c7f2393; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_scopedrole_tenant_id_1c7f2393 ON public.accounts_scopedrole USING btree (tenant_id);


--
-- Name: accounts_scopedrole_user_id_739af120; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_scopedrole_user_id_739af120 ON public.accounts_scopedrole USING btree (user_id);


--
-- Name: accounts_tenant_name_62906664_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_tenant_name_62906664_like ON public.accounts_tenant USING btree (name varchar_pattern_ops);


--
-- Name: accounts_user_groups_group_id_bd11a704; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_user_groups_group_id_bd11a704 ON public.accounts_user_groups USING btree (group_id);


--
-- Name: accounts_user_groups_user_id_52b62117; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_user_groups_user_id_52b62117 ON public.accounts_user_groups USING btree (user_id);


--
-- Name: accounts_user_tenant_id_1906c0a8; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_user_tenant_id_1906c0a8 ON public.accounts_user USING btree (tenant_id);


--
-- Name: accounts_user_user_permissions_permission_id_113bb443; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_user_user_permissions_permission_id_113bb443 ON public.accounts_user_user_permissions USING btree (permission_id);


--
-- Name: accounts_user_user_permissions_user_id_e4f0a161; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_user_user_permissions_user_id_e4f0a161 ON public.accounts_user_user_permissions USING btree (user_id);


--
-- Name: accounts_user_username_6088629e_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_user_username_6088629e_like ON public.accounts_user USING btree (username varchar_pattern_ops);


--
-- Name: ai_copilot__project_243753_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_copilot__project_243753_idx ON public.ai_copilot_proactiveinsight USING btree (project_id, created_at DESC);


--
-- Name: ai_copilot__project_27b666_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_copilot__project_27b666_idx ON public.ai_copilot_conversationmessage USING btree (project_id, created_at DESC);


--
-- Name: ai_copilot__user_id_2ff702_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_copilot__user_id_2ff702_idx ON public.ai_copilot_proactiveinsight USING btree (user_id, acknowledged, created_at DESC);


--
-- Name: ai_copilot__user_id_7ac4e4_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_copilot__user_id_7ac4e4_idx ON public.ai_copilot_conversationmessage USING btree (user_id, created_at DESC);


--
-- Name: ai_copilot_conversationmessage_project_id_34619dd3; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_copilot_conversationmessage_project_id_34619dd3 ON public.ai_copilot_conversationmessage USING btree (project_id);


--
-- Name: ai_copilot_conversationmessage_user_id_e9c0469d; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_copilot_conversationmessage_user_id_e9c0469d ON public.ai_copilot_conversationmessage USING btree (user_id);


--
-- Name: ai_copilot_proactiveinsight_project_id_e67c32a7; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_copilot_proactiveinsight_project_id_e67c32a7 ON public.ai_copilot_proactiveinsight USING btree (project_id);


--
-- Name: ai_copilot_proactiveinsight_user_id_fbf921b1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ai_copilot_proactiveinsight_user_id_fbf921b1 ON public.ai_copilot_proactiveinsight USING btree (user_id);


--
-- Name: auth_group_name_a6ea08ec_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_name_a6ea08ec_like ON public.auth_group USING btree (name varchar_pattern_ops);


--
-- Name: auth_group_permissions_group_id_b120cbf9; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_permissions_group_id_b120cbf9 ON public.auth_group_permissions USING btree (group_id);


--
-- Name: auth_group_permissions_permission_id_84c5c92e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_permissions_permission_id_84c5c92e ON public.auth_group_permissions USING btree (permission_id);


--
-- Name: auth_permission_content_type_id_2f476e4b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_permission_content_type_id_2f476e4b ON public.auth_permission USING btree (content_type_id);


--
-- Name: core_module_project_id_63dc3a7f; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX core_module_project_id_63dc3a7f ON public.core_module USING btree (project_id);


--
-- Name: core_project_tenant_id_560cac1a; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX core_project_tenant_id_560cac1a ON public.core_project USING btree (tenant_id);


--
-- Name: dataschema_datafield_created_by_id_ae56955f; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_datafield_created_by_id_ae56955f ON public.dataschema_datafield USING btree (created_by_id);


--
-- Name: dataschema_datafield_data_table_id_8c790d12; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_datafield_data_table_id_8c790d12 ON public.dataschema_datafield USING btree (data_table_id);


--
-- Name: dataschema_datafield_reference_table_id_e1ddcd6d; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_datafield_reference_table_id_e1ddcd6d ON public.dataschema_datafield USING btree (reference_table_id);


--
-- Name: dataschema_datafield_updated_by_id_81c3db8e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_datafield_updated_by_id_81c3db8e ON public.dataschema_datafield USING btree (updated_by_id);


--
-- Name: dataschema_datarow_created_by_id_e77d0dd9; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_datarow_created_by_id_e77d0dd9 ON public.dataschema_datarow USING btree (created_by_id);


--
-- Name: dataschema_datarow_data_table_id_7b1671a8; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_datarow_data_table_id_7b1671a8 ON public.dataschema_datarow USING btree (data_table_id);


--
-- Name: dataschema_datarow_updated_by_id_1a3ab18c; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_datarow_updated_by_id_1a3ab18c ON public.dataschema_datarow USING btree (updated_by_id);


--
-- Name: dataschema_datatable_created_by_id_48dbe5dd; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_datatable_created_by_id_48dbe5dd ON public.dataschema_datatable USING btree (created_by_id);


--
-- Name: dataschema_datatable_module_id_c6e4e57a; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_datatable_module_id_c6e4e57a ON public.dataschema_datatable USING btree (module_id);


--
-- Name: dataschema_datatable_name_13303929; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_datatable_name_13303929 ON public.dataschema_datatable USING btree (name);


--
-- Name: dataschema_datatable_name_13303929_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_datatable_name_13303929_like ON public.dataschema_datatable USING btree (name varchar_pattern_ops);


--
-- Name: dataschema_datatable_updated_by_id_9f76f540; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_datatable_updated_by_id_9f76f540 ON public.dataschema_datatable USING btree (updated_by_id);


--
-- Name: dataschema_schemachangelog_data_field_id_34bef2f5; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_schemachangelog_data_field_id_34bef2f5 ON public.dataschema_schemachangelog USING btree (data_field_id);


--
-- Name: dataschema_schemachangelog_data_table_id_d5e079de; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_schemachangelog_data_table_id_d5e079de ON public.dataschema_schemachangelog USING btree (data_table_id);


--
-- Name: dataschema_schemachangelog_user_id_010cccc3; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dataschema_schemachangelog_user_id_010cccc3 ON public.dataschema_schemachangelog USING btree (user_id);


--
-- Name: django_admin_log_content_type_id_c4bce8eb; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_admin_log_content_type_id_c4bce8eb ON public.django_admin_log USING btree (content_type_id);


--
-- Name: django_admin_log_user_id_c564eba6; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_admin_log_user_id_c564eba6 ON public.django_admin_log USING btree (user_id);


--
-- Name: django_session_expire_date_a5c62663; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_session_expire_date_a5c62663 ON public.django_session USING btree (expire_date);


--
-- Name: django_session_session_key_c0390e0f_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_session_session_key_c0390e0f_like ON public.django_session USING btree (session_key varchar_pattern_ops);


--
-- Name: token_blacklist_outstandingtoken_jti_hex_d9bdf6f7_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX token_blacklist_outstandingtoken_jti_hex_d9bdf6f7_like ON public.token_blacklist_outstandingtoken USING btree (jti varchar_pattern_ops);


--
-- Name: token_blacklist_outstandingtoken_user_id_83bc629a; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX token_blacklist_outstandingtoken_user_id_83bc629a ON public.token_blacklist_outstandingtoken USING btree (user_id);


--
-- Name: accounts_roleassignmentauditlog accounts_roleassignm_actor_id_8dc20397_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_roleassignmentauditlog
    ADD CONSTRAINT accounts_roleassignm_actor_id_8dc20397_fk_accounts_ FOREIGN KEY (actor_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_roleassignmentauditlog accounts_roleassignm_group_id_0f6b152e_fk_auth_grou; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_roleassignmentauditlog
    ADD CONSTRAINT accounts_roleassignm_group_id_0f6b152e_fk_auth_grou FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_roleassignmentauditlog accounts_roleassignm_module_id_584e05ea_fk_core_modu; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_roleassignmentauditlog
    ADD CONSTRAINT accounts_roleassignm_module_id_584e05ea_fk_core_modu FOREIGN KEY (module_id) REFERENCES public.core_module(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_roleassignmentauditlog accounts_roleassignm_project_id_cb535b5f_fk_core_proj; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_roleassignmentauditlog
    ADD CONSTRAINT accounts_roleassignm_project_id_cb535b5f_fk_core_proj FOREIGN KEY (project_id) REFERENCES public.core_project(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_roleassignmentauditlog accounts_roleassignm_tenant_id_54dff115_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_roleassignmentauditlog
    ADD CONSTRAINT accounts_roleassignm_tenant_id_54dff115_fk_accounts_ FOREIGN KEY (tenant_id) REFERENCES public.accounts_tenant(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_roleassignmentauditlog accounts_roleassignm_user_id_e2fac962_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_roleassignmentauditlog
    ADD CONSTRAINT accounts_roleassignm_user_id_e2fac962_fk_accounts_ FOREIGN KEY (user_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_scopedrole accounts_scopedrole_group_id_cf584c29_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_scopedrole
    ADD CONSTRAINT accounts_scopedrole_group_id_cf584c29_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_scopedrole accounts_scopedrole_module_id_8b78908b_fk_core_module_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_scopedrole
    ADD CONSTRAINT accounts_scopedrole_module_id_8b78908b_fk_core_module_id FOREIGN KEY (module_id) REFERENCES public.core_module(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_scopedrole accounts_scopedrole_project_id_c1692ed0_fk_core_project_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_scopedrole
    ADD CONSTRAINT accounts_scopedrole_project_id_c1692ed0_fk_core_project_id FOREIGN KEY (project_id) REFERENCES public.core_project(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_scopedrole accounts_scopedrole_tenant_id_1c7f2393_fk_accounts_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_scopedrole
    ADD CONSTRAINT accounts_scopedrole_tenant_id_1c7f2393_fk_accounts_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.accounts_tenant(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_scopedrole accounts_scopedrole_user_id_739af120_fk_accounts_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_scopedrole
    ADD CONSTRAINT accounts_scopedrole_user_id_739af120_fk_accounts_user_id FOREIGN KEY (user_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_user_groups accounts_user_groups_group_id_bd11a704_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_user_groups
    ADD CONSTRAINT accounts_user_groups_group_id_bd11a704_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_user_groups accounts_user_groups_user_id_52b62117_fk_accounts_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_user_groups
    ADD CONSTRAINT accounts_user_groups_user_id_52b62117_fk_accounts_user_id FOREIGN KEY (user_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_user accounts_user_tenant_id_1906c0a8_fk_accounts_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_user
    ADD CONSTRAINT accounts_user_tenant_id_1906c0a8_fk_accounts_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.accounts_tenant(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_user_user_permissions accounts_user_user_p_permission_id_113bb443_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_user_user_permissions
    ADD CONSTRAINT accounts_user_user_p_permission_id_113bb443_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: accounts_user_user_permissions accounts_user_user_p_user_id_e4f0a161_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_user_user_permissions
    ADD CONSTRAINT accounts_user_user_p_user_id_e4f0a161_fk_accounts_ FOREIGN KEY (user_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: ai_copilot_conversationmessage ai_copilot_conversat_project_id_34619dd3_fk_core_proj; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_copilot_conversationmessage
    ADD CONSTRAINT ai_copilot_conversat_project_id_34619dd3_fk_core_proj FOREIGN KEY (project_id) REFERENCES public.core_project(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: ai_copilot_conversationmessage ai_copilot_conversat_user_id_e9c0469d_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_copilot_conversationmessage
    ADD CONSTRAINT ai_copilot_conversat_user_id_e9c0469d_fk_accounts_ FOREIGN KEY (user_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: ai_copilot_proactiveinsight ai_copilot_proactive_project_id_e67c32a7_fk_core_proj; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_copilot_proactiveinsight
    ADD CONSTRAINT ai_copilot_proactive_project_id_e67c32a7_fk_core_proj FOREIGN KEY (project_id) REFERENCES public.core_project(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: ai_copilot_proactiveinsight ai_copilot_proactive_user_id_fbf921b1_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_copilot_proactiveinsight
    ADD CONSTRAINT ai_copilot_proactive_user_id_fbf921b1_fk_accounts_ FOREIGN KEY (user_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: ai_copilot_useraipreference ai_copilot_useraipre_user_id_9deba3cb_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_copilot_useraipreference
    ADD CONSTRAINT ai_copilot_useraipre_user_id_9deba3cb_fk_accounts_ FOREIGN KEY (user_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissio_permission_id_84c5c92e_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissio_permission_id_84c5c92e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissions_group_id_b120cbf9_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_permission auth_permission_content_type_id_2f476e4b_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_module core_module_project_id_63dc3a7f_fk_core_project_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.core_module
    ADD CONSTRAINT core_module_project_id_63dc3a7f_fk_core_project_id FOREIGN KEY (project_id) REFERENCES public.core_project(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_project core_project_tenant_id_560cac1a_fk_accounts_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.core_project
    ADD CONSTRAINT core_project_tenant_id_560cac1a_fk_accounts_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.accounts_tenant(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: dataschema_datafield dataschema_datafield_created_by_id_ae56955f_fk_accounts_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datafield
    ADD CONSTRAINT dataschema_datafield_created_by_id_ae56955f_fk_accounts_user_id FOREIGN KEY (created_by_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: dataschema_datafield dataschema_datafield_data_table_id_8c790d12_fk_dataschem; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datafield
    ADD CONSTRAINT dataschema_datafield_data_table_id_8c790d12_fk_dataschem FOREIGN KEY (data_table_id) REFERENCES public.dataschema_datatable(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: dataschema_datafield dataschema_datafield_reference_table_id_e1ddcd6d_fk_dataschem; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datafield
    ADD CONSTRAINT dataschema_datafield_reference_table_id_e1ddcd6d_fk_dataschem FOREIGN KEY (reference_table_id) REFERENCES public.dataschema_datatable(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: dataschema_datafield dataschema_datafield_updated_by_id_81c3db8e_fk_accounts_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datafield
    ADD CONSTRAINT dataschema_datafield_updated_by_id_81c3db8e_fk_accounts_user_id FOREIGN KEY (updated_by_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: dataschema_datarow dataschema_datarow_created_by_id_e77d0dd9_fk_accounts_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datarow
    ADD CONSTRAINT dataschema_datarow_created_by_id_e77d0dd9_fk_accounts_user_id FOREIGN KEY (created_by_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: dataschema_datarow dataschema_datarow_data_table_id_7b1671a8_fk_dataschem; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datarow
    ADD CONSTRAINT dataschema_datarow_data_table_id_7b1671a8_fk_dataschem FOREIGN KEY (data_table_id) REFERENCES public.dataschema_datatable(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: dataschema_datarow dataschema_datarow_updated_by_id_1a3ab18c_fk_accounts_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datarow
    ADD CONSTRAINT dataschema_datarow_updated_by_id_1a3ab18c_fk_accounts_user_id FOREIGN KEY (updated_by_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: dataschema_datatable dataschema_datatable_created_by_id_48dbe5dd_fk_accounts_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datatable
    ADD CONSTRAINT dataschema_datatable_created_by_id_48dbe5dd_fk_accounts_user_id FOREIGN KEY (created_by_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: dataschema_datatable dataschema_datatable_module_id_c6e4e57a_fk_core_module_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datatable
    ADD CONSTRAINT dataschema_datatable_module_id_c6e4e57a_fk_core_module_id FOREIGN KEY (module_id) REFERENCES public.core_module(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: dataschema_datatable dataschema_datatable_updated_by_id_9f76f540_fk_accounts_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_datatable
    ADD CONSTRAINT dataschema_datatable_updated_by_id_9f76f540_fk_accounts_user_id FOREIGN KEY (updated_by_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: dataschema_schemachangelog dataschema_schemacha_data_field_id_34bef2f5_fk_dataschem; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_schemachangelog
    ADD CONSTRAINT dataschema_schemacha_data_field_id_34bef2f5_fk_dataschem FOREIGN KEY (data_field_id) REFERENCES public.dataschema_datafield(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: dataschema_schemachangelog dataschema_schemacha_data_table_id_d5e079de_fk_dataschem; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_schemachangelog
    ADD CONSTRAINT dataschema_schemacha_data_table_id_d5e079de_fk_dataschem FOREIGN KEY (data_table_id) REFERENCES public.dataschema_datatable(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: dataschema_schemachangelog dataschema_schemachangelog_user_id_010cccc3_fk_accounts_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataschema_schemachangelog
    ADD CONSTRAINT dataschema_schemachangelog_user_id_010cccc3_fk_accounts_user_id FOREIGN KEY (user_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log django_admin_log_content_type_id_c4bce8eb_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_content_type_id_c4bce8eb_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log django_admin_log_user_id_c564eba6_fk_accounts_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_user_id_c564eba6_fk_accounts_user_id FOREIGN KEY (user_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: token_blacklist_blacklistedtoken token_blacklist_blacklistedtoken_token_id_3cc7fe56_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_blacklist_blacklistedtoken
    ADD CONSTRAINT token_blacklist_blacklistedtoken_token_id_3cc7fe56_fk FOREIGN KEY (token_id) REFERENCES public.token_blacklist_outstandingtoken(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: token_blacklist_outstandingtoken token_blacklist_outs_user_id_83bc629a_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_blacklist_outstandingtoken
    ADD CONSTRAINT token_blacklist_outs_user_id_83bc629a_fk_accounts_ FOREIGN KEY (user_id) REFERENCES public.accounts_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- PostgreSQL database dump complete
--

\unrestrict XE8gsjNMsyIncbiIOjk3Ea1vDDEAHzF9jNY9NJbvMM4jRLzzZ6VymTjBWNTbSLc

