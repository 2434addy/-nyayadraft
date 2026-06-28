import { supabase } from "./supabase";

/** A persisted draft row. Mirrors the `drafts` table (see supabase/schema.sql). */
export interface Draft {
  id: string;
  user_id: string;
  doc_type: string;
  doc_type_label: string;
  fields: Record<string, string>;
  generated_text: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface NewDraftInput {
  user_id: string;
  doc_type: string;
  doc_type_label: string;
  fields: Record<string, string>;
  generated_text: string;
  title: string;
}

/** All drafts for the signed-in user, newest first. RLS scopes rows to the user. */
export async function listDrafts(): Promise<Draft[]> {
  const { data, error } = await supabase
    .from("drafts")
    .select("*")
    .order("updated_at", { ascending: false });
  if (error) throw new Error(error.message);
  return (data ?? []) as Draft[];
}

/** Insert a new draft and return the persisted row. */
export async function createDraft(input: NewDraftInput): Promise<Draft> {
  const { data, error } = await supabase
    .from("drafts")
    .insert(input)
    .select()
    .single();
  if (error) throw new Error(error.message);
  return data as Draft;
}

/** Rename a draft (title only). */
export async function renameDraft(id: string, title: string): Promise<void> {
  const { error } = await supabase
    .from("drafts")
    .update({ title, updated_at: new Date().toISOString() })
    .eq("id", id);
  if (error) throw new Error(error.message);
}

/** Permanently delete a draft. */
export async function deleteDraft(id: string): Promise<void> {
  const { error } = await supabase.from("drafts").delete().eq("id", id);
  if (error) throw new Error(error.message);
}
