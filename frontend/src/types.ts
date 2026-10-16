export type Project = {id: string; name: string; source_filename: string | null; status: string; assembly_status: string; final_output: string | null; assembly_error: string | null; created_at: string; updated_at: string};
export type Character = {id: string; name: string; age: number | null; description: string; reference_image: string | null; positive_prompt: string; default_ipadapter_weight: number};
export type Shot = {id: string; code: string; sequence: number; action: string; shot_type: string; motion_mode: string; workflow_key: string; status: string; positive_prompt: string; negative_prompt: string; output_file: string | null};
export type Motion = {id: string; motion_id: string; name: string; action: string; speed: string; direction: string; source_file: string; tags: string[]};
export type Job = {id: string; shot_id: string; worker_name: string | null; status: string; attempt: number; error_message: string | null; created_at: string};

