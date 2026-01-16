import { useForm } from "react-hook-form"
import { useLanguages } from "../../contexts/LanguageContext";
import { type CreateNovel } from "../../types/novel";
import { create_novel } from "../../api/novels";
import type React from "react";

type Props = { onClose: () => void };

const formStyles: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
    padding: '0.5rem 0',
};

const inputStyles: React.CSSProperties = {
    padding: '0.625rem 0.75rem',
    fontSize: '0.95rem',
    border: '1px solid #ccc',
    borderRadius: '6px',
    outline: 'none',
};

const labelStyles: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.35rem',
    fontSize: '0.875rem',
    fontWeight: 500,
    color: '#333',
};

const rowStyles: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '1rem',
};

const buttonRowStyles: React.CSSProperties = {
    display: 'flex',
    gap: '0.75rem',
    marginTop: '0.5rem',
    justifyContent: 'flex-end',
};

const primaryButtonStyles: React.CSSProperties = {
    padding: '0.625rem 1.25rem',
    fontSize: '0.95rem',
    fontWeight: 500,
    color: '#fff',
    backgroundColor: '#2563eb',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
};

const secondaryButtonStyles: React.CSSProperties = {
    padding: '0.625rem 1.25rem',
    fontSize: '0.95rem',
    fontWeight: 500,
    color: '#333',
    backgroundColor: '#e5e7eb',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
};

export const CreateNovelForm: React.FC<Props> = ({ onClose }) => {
    const languages = useLanguages();
    const { register, handleSubmit, reset, formState: { isSubmitting } } = useForm<CreateNovel>();

    const onSubmit = async (data: CreateNovel) => {
        try {
            const newNovel = await create_novel(data);
            alert(`Novel "${newNovel.novel_title}" created successfully!`);
            reset();
            onClose();
        } catch (error) {
            console.error("Error creating novel:", error);
            alert("Failed to create novel. Please try again.");
        }
    };

    return (
        <form onSubmit={handleSubmit(onSubmit)} style={formStyles}>
            <label style={labelStyles}>
                Title *
                <input 
                    {...register('novel_title', { required: true, maxLength: 255 })} 
                    placeholder="Enter novel title"
                    style={inputStyles}
                />
            </label>

            <label style={labelStyles}>
                Description
                <textarea 
                    {...register('novel_description')} 
                    placeholder="Enter description (optional)"
                    rows={3}
                    style={{ ...inputStyles, resize: 'vertical' }}
                />
            </label>

            <div style={rowStyles}>
                <label style={labelStyles}>
                    Author
                    <input 
                        {...register('novel_author')} 
                        placeholder="Author name"
                        style={inputStyles}
                    />
                </label>

                <label style={labelStyles}>
                    Type *
                    <select {...register('novel_type', { required: true })} style={inputStyles}>
                        <option value="">Select type</option>
                        <option value="original">Original</option>
                        <option value="translation">Translation</option>
                        <option value="other">Other</option>
                    </select>
                </label>
            </div>

            <div style={rowStyles}>
                <label style={labelStyles}>
                    Visibility *
                    <select {...register('novel_visibility', { required: true, valueAsNumber: true })} style={inputStyles}>
                        <option value="">Select visibility</option>
                        <option value={0}>Private</option>
                        <option value={1}>Restricted</option>
                        <option value={2}>Unlisted</option>
                        <option value={3}>Public</option>
                    </select>
                </label>

                <label style={labelStyles}>
                    Language *
                    <select {...register('language_code', { required: true })} style={inputStyles}>
                        <option value="">Select language</option>
                        {languages.map(lang => (
                            <option key={lang.language_code} value={lang.language_code}>
                                {lang.language_name}
                            </option>
                        ))}
                    </select>
                </label>
            </div>

            <div style={buttonRowStyles}>
                <button
                    type="button"
                    onClick={() => { reset(); onClose(); }}
                    style={secondaryButtonStyles}
                >
                    Cancel
                </button>
                <button type="submit" disabled={isSubmitting} style={primaryButtonStyles}>
                    {isSubmitting ? 'Creating...' : 'Create Novel'}
                </button>
            </div>
        </form>
    );
}