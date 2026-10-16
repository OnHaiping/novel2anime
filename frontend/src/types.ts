export type Project = {id: string; name: string; source_filename: string | null; settings: Record<string, unknown>; status: string; assembly_status: string; final_output: string | null; assembly_error: string | null; created_at: string; updated_at: string};
export type Character = {id: string; name: string; age: number | null; description: string; reference_image: string | null; positive_prompt: string; default_ipadapter_weight: number};
export type NovelContent = {novel_type: 'long' | 'short'; text: string; length: number; max_selection_chars: number};
export type NovelSelection = {id: string; sequence: number; title: string; source_text: string; char_start: number; char_end: number; selected: boolean; summary: string; process_count: number; last_processed_at: string | null};
export type Shot = {id: string; code: string; sequence: number; action: string; shot_type: string; motion_mode: string; workflow_key: string; status: string; positive_prompt: string; negative_prompt: string; output_file: string | null};
export type Motion = {id: string; motion_id: string; name: string; action: string; speed: string; direction: string; source_file: string; tags: string[]};
export type Job = {id: string; shot_id: string; worker_name: string | null; status: string; attempt: number; error_message: string | null; created_at: string};
export type AssetJob = {id: string; job_type: string; project_id: string | null; character_id: string | null; worker_name: string | null; status: string; error_message: string | null; created_at: string; output_metadata: Record<string, unknown>};
export type ModelStatus = {key: string; name: string; url: string; target: string; path: string; exists: boolean; size: number};

