import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, X, FileText, AlertCircle, Paperclip } from 'lucide-react';
import type { UploadedFile } from '../../types';
import { uploadFile } from '../../api/files';
import { formatFileSize, getFileIcon, getFileExtension } from '../../utils/formatters';
import { ACCEPTED_FILE_TYPES, FILE_SIZE_LIMIT } from '../../utils/constants';
import toast from 'react-hot-toast';
import { getApiErrorMessage } from '../../utils/errors';

interface FileUploadZoneProps {
  onFilesUploaded: (files: UploadedFile[]) => void;
  uploadedFiles: UploadedFile[];
  onRemoveFile: (fileId: number) => void;
  maxFiles?: number;
}

interface UploadingFile {
  name: string;
  size: number;
  progress: number;
  error?: string;
}

export const FileUploadZone: React.FC<FileUploadZoneProps> = ({
  onFilesUploaded,
  uploadedFiles,
  onRemoveFile,
  maxFiles = 10,
}) => {
  const [uploadingFiles, setUploadingFiles] = useState<
    Record<string, UploadingFile>
  >({});

  const handleDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (uploadedFiles.length + acceptedFiles.length > maxFiles) {
        toast.error(`最多上传 ${maxFiles} 个文件`);
        return;
      }

      const newUploading: Record<string, UploadingFile> = {};
      acceptedFiles.forEach((file) => {
        newUploading[file.name] = { name: file.name, size: file.size, progress: 0 };
      });
      setUploadingFiles((prev) => ({ ...prev, ...newUploading }));

      const uploadedResults: UploadedFile[] = [];

      for (const file of acceptedFiles) {
        if (file.size > FILE_SIZE_LIMIT) {
          setUploadingFiles((prev) => ({
            ...prev,
            [file.name]: { ...prev[file.name], error: '文件超过 50MB 限制' },
          }));
          continue;
        }

        try {
          const result = await uploadFile(file, (progress) => {
            setUploadingFiles((prev) => ({
              ...prev,
              [file.name]: { ...prev[file.name], progress },
            }));
          });
          uploadedResults.push(result);

          setUploadingFiles((prev) => {
            const next = { ...prev };
            delete next[file.name];
            return next;
          });
        } catch (err: any) {
          const errorMsg = getApiErrorMessage(err, '上传失败');
          setUploadingFiles((prev) => ({
            ...prev,
            [file.name]: { ...prev[file.name], error: errorMsg },
          }));
          toast.error(`${file.name} 上传失败：${errorMsg}`);
        }
      }

      if (uploadedResults.length > 0) {
        onFilesUploaded(uploadedResults);
        toast.success(`成功上传 ${uploadedResults.length} 个文件`);
      }
    },
    [uploadedFiles.length, maxFiles, onFilesUploaded]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: FILE_SIZE_LIMIT,
    multiple: true,
  });

  const isUploading = Object.keys(uploadingFiles).length > 0;

  return (
    <div className="space-y-3">
      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={[
          'group relative rounded-xl border-2 border-dashed px-6 py-8 text-center cursor-pointer transition-all duration-200',
          isDragActive
            ? 'border-brand bg-brand-soft/60'
            : 'border-line bg-elevated hover:border-line-strong hover:bg-surface',
        ].join(' ')}
      >
        <input {...getInputProps()} />

        <div className="flex flex-col items-center gap-3">
          <div
            className={[
              'flex h-14 w-14 items-center justify-center rounded-full transition-colors',
              isDragActive
                ? 'bg-brand text-ink-inverse'
                : 'bg-sunken text-ink-3 group-hover:bg-brand-soft group-hover:text-brand',
            ].join(' ')}
          >
            <Upload size={22} />
          </div>
          <div className="space-y-1">
            <p
              className={[
                'text-[13.5px] font-medium',
                isDragActive ? 'text-brand' : 'text-ink-2',
              ].join(' ')}
            >
              {isDragActive ? '释放以添加文件' : '拖拽文件到此处，或点击选择文件'}
            </p>
            <p className="text-[12px] text-ink-3">
              支持 PDF · Word · Excel · PPT · TXT · CSV · JSON · 图片 等，单文件上限 50MB
            </p>
          </div>
        </div>
      </div>

      {/* Uploading files */}
      <AnimatePresence>
        {isUploading &&
          Object.values(uploadingFiles).map((uf) => (
            <motion.div
              key={uf.name}
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, height: 0 }}
              className="ds-card flex items-center gap-3 p-3"
            >
              <span className="text-xl" aria-hidden>
                {getFileIcon(uf.name)}
              </span>
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="truncate text-[13.5px] text-ink-1">{uf.name}</span>
                  <span className="flex-shrink-0 text-[11.5px] text-ink-3">
                    {formatFileSize(uf.size)}
                  </span>
                </div>
                {uf.error ? (
                  <div className="flex items-center gap-1 text-[12px] text-danger">
                    <AlertCircle size={12} />
                    <span>{uf.error}</span>
                  </div>
                ) : (
                  <div className="h-1.5 overflow-hidden rounded-full bg-sunken">
                    <div
                      className="h-full rounded-full bg-brand transition-all duration-300"
                      style={{ width: `${uf.progress}%` }}
                    />
                  </div>
                )}
              </div>
              {uf.error && (
                <button
                  onClick={() =>
                    setUploadingFiles((prev) => {
                      const next = { ...prev };
                      delete next[uf.name];
                      return next;
                    })
                  }
                  className="rounded-md p-1 text-ink-3 transition-colors hover:bg-sunken hover:text-ink-1"
                  aria-label="移除"
                >
                  <X size={15} />
                </button>
              )}
            </motion.div>
          ))}
      </AnimatePresence>

      {/* Uploaded files */}
      <AnimatePresence>
        {uploadedFiles.map((file) => (
          <motion.div
            key={file.id}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, height: 0 }}
            className="ds-card ds-card-hover flex items-center gap-3 p-3"
          >
            <span className="text-xl" aria-hidden>
              {getFileIcon(file.original_name)}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-[13.5px] text-ink-1">
                  {file.original_name}
                </span>
                <span className="flex-shrink-0 text-[11.5px] text-ink-3">
                  {formatFileSize(file.file_size)}
                </span>
              </div>
              <div className="mt-0.5 flex items-center gap-2 text-[11.5px]">
                <span className="uppercase tracking-wider text-ink-4">
                  {getFileExtension(file.original_name)}
                </span>
                {file.extracted_text && (
                  <span className="inline-flex items-center gap-1 text-success">
                    <FileText size={10} />
                    已提取文本
                  </span>
                )}
                <span className="inline-flex items-center gap-1 text-ink-4">
                  <Paperclip size={10} />
                  已附加
                </span>
              </div>
            </div>
            <button
              onClick={() => onRemoveFile(file.id)}
              className="flex-shrink-0 rounded-md p-1 text-ink-3 transition-colors hover:bg-danger-soft hover:text-danger"
              aria-label="移除文件"
            >
              <X size={15} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
};

export default FileUploadZone;
