"""Model for Sublime Security Organization Settings."""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class AuditEventsExport:
    """Audit events export configuration."""
    
    export_s3_bucket_name: Optional[str] = None
    export_s3_key_prefix: Optional[str] = None
    export_s3_region: Optional[str] = None
    export_format: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> "AuditEventsExport":
        """Create AuditEventsExport from dictionary."""
        if not data:
            return cls()
        
        return cls(
            export_s3_bucket_name=data.get("export_s3_bucket_name"),
            export_s3_key_prefix=data.get("export_s3_key_prefix"),
            export_s3_region=data.get("export_s3_region"),
            export_format=data.get("export_format")
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        result = {}
        if self.export_s3_bucket_name:
            result["export_s3_bucket_name"] = self.export_s3_bucket_name
        if self.export_s3_key_prefix:
            result["export_s3_key_prefix"] = self.export_s3_key_prefix
        if self.export_s3_region:
            result["export_s3_region"] = self.export_s3_region
        if self.export_format:
            result["export_format"] = self.export_format
        return result


@dataclass
class MessageExport:
    """Message export configuration."""
    
    message_export_s3_bucket_name: Optional[str] = None
    message_export_s3_key_prefix: Optional[str] = None
    message_export_s3_region: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MessageExport":
        """Create MessageExport from dictionary."""
        if not data:
            return cls()
        
        return cls(
            message_export_s3_bucket_name=data.get("message_export_s3_bucket_name"),
            message_export_s3_key_prefix=data.get("message_export_s3_key_prefix"),
            message_export_s3_region=data.get("message_export_s3_region")
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        result = {}
        if self.message_export_s3_bucket_name:
            result["message_export_s3_bucket_name"] = self.message_export_s3_bucket_name
        if self.message_export_s3_key_prefix:
            result["message_export_s3_key_prefix"] = self.message_export_s3_key_prefix
        if self.message_export_s3_region:
            result["message_export_s3_region"] = self.message_export_s3_region
        return result


@dataclass
class OIDCConfig:
    """OIDC configuration."""
    
    issuer_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    initiate_login_url: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> "OIDCConfig":
        """Create OIDCConfig from dictionary."""
        if not data:
            return cls()
        
        return cls(
            issuer_url=data.get("issuer_url"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            redirect_uri=data.get("redirect_uri"),
            initiate_login_url=data.get("initiate_login_url")
        )
    
    def to_dict(self, include_sensitive: bool = False) -> Dict:
        """Convert to dictionary."""
        result = {}
        if self.issuer_url:
            result["issuer_url"] = self.issuer_url
        if self.client_id:
            result["client_id"] = self.client_id
        if include_sensitive and self.client_secret:
            result["client_secret"] = self.client_secret
        if self.redirect_uri:
            result["redirect_uri"] = self.redirect_uri
        if self.initiate_login_url:
            result["initiate_login_url"] = self.initiate_login_url
        return result


@dataclass
class SAMLConfig:
    """SAML configuration."""
    
    metadata_url: Optional[str] = None
    sso_url: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SAMLConfig":
        """Create SAMLConfig from dictionary."""
        if not data:
            return cls()
        
        return cls(
            metadata_url=data.get("metadata_url"),
            sso_url=data.get("sso_url")
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        result = {}
        if self.metadata_url:
            result["metadata_url"] = self.metadata_url
        if self.sso_url:
            result["sso_url"] = self.sso_url
        return result


@dataclass
class TelemetryConfig:
    """Telemetry configuration."""
    
    telemetry_share_with_sublime: bool = False
    telemetry_product_usage: bool = False
    telemetry_errors_usage: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TelemetryConfig":
        """Create TelemetryConfig from dictionary."""
        if not data:
            return cls()
        
        return cls(
            telemetry_share_with_sublime=data.get("telemetry_share_with_sublime", False),
            telemetry_product_usage=data.get("telemetry_product_usage", False),
            telemetry_errors_usage=data.get("telemetry_errors_usage", True)
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "telemetry_share_with_sublime": self.telemetry_share_with_sublime,
            "telemetry_product_usage": self.telemetry_product_usage,
            "telemetry_errors_usage": self.telemetry_errors_usage
        }


@dataclass
class IPAllowlistEntry:
    """IP allowlist entry."""
    
    ip: str
    notes: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> "IPAllowlistEntry":
        """Create IPAllowlistEntry from dictionary."""
        return cls(
            ip=data.get("ip", ""),
            notes=data.get("notes")
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        result = {"ip": self.ip}
        if self.notes:
            result["notes"] = self.notes
        return result


@dataclass
class OrganizationSettings:
    """Organization settings for Sublime Security."""
    
    # Identity provider settings
    allowed_identity_providers: Optional[List[str]] = None
    oidc_config: Optional[OIDCConfig] = None
    saml_config: Optional[SAMLConfig] = None
    
    # Mailbox and processing settings
    auto_activate_synced_mailboxes: bool = True
    enable_inline_processing: bool = False
    
    # Retention settings
    mdm_retention_days: int = 30
    full_message_retention_days: int = 30
    flagged_or_reported_message_retention_days: int = 1825
    
    # Abuse and security settings
    abuse_mailboxes: Optional[List[str]] = None
    allow_unauthenticated_user_reports: bool = False
    require_message_access_justification: bool = True
    
    # IP allowlist
    ip_allowlist_json: Optional[List[IPAllowlistEntry]] = None
    
    # Export configurations
    audit_events_export: Optional[AuditEventsExport] = None
    message_export: Optional[MessageExport] = None
    
    # Telemetry settings
    telemetry: Optional[TelemetryConfig] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> "OrganizationSettings":
        """Create OrganizationSettings from dictionary."""
        # Parse IP allowlist
        ip_allowlist = None
        if data.get("ip_allowlist_json"):
            ip_allowlist = [
                IPAllowlistEntry.from_dict(entry) 
                for entry in data["ip_allowlist_json"]
            ]
        
        return cls(
            allowed_identity_providers=data.get("allowed_identity_providers"),
            oidc_config=OIDCConfig.from_dict(data.get("oidc_config", {})),
            saml_config=SAMLConfig.from_dict(data.get("saml_config", {})),
            auto_activate_synced_mailboxes=data.get("auto_activate_synced_mailboxes", True),
            enable_inline_processing=data.get("enable_inline_processing", False),
            mdm_retention_days=data.get("mdm_retention_days", 30),
            full_message_retention_days=data.get("full_message_retention_days", 30),
            flagged_or_reported_message_retention_days=data.get("flagged_or_reported_message_retention_days", 1825),
            abuse_mailboxes=data.get("abuse_mailboxes"),
            allow_unauthenticated_user_reports=data.get("allow_unauthenticated_user_reports", False),
            require_message_access_justification=data.get("require_message_access_justification", True),
            ip_allowlist_json=ip_allowlist,
            audit_events_export=AuditEventsExport.from_dict(data.get("audit_events_export", {})),
            message_export=MessageExport.from_dict(data.get("message_export", {})),
            telemetry=TelemetryConfig.from_dict(data.get("telemetry", {}))
        )
    
    def to_dict(self, include_sensitive: bool = False) -> Dict:
        """Convert to dictionary."""
        result = {}
        
        # Identity providers
        if self.allowed_identity_providers:
            result["allowed_identity_providers"] = self.allowed_identity_providers
        
        if self.oidc_config:
            oidc_dict = self.oidc_config.to_dict(include_sensitive=include_sensitive)
            if oidc_dict:
                result["oidc_config"] = oidc_dict
        
        if self.saml_config:
            saml_dict = self.saml_config.to_dict()
            if saml_dict:
                result["saml_config"] = saml_dict
        
        # Basic settings
        result["auto_activate_synced_mailboxes"] = self.auto_activate_synced_mailboxes
        result["enable_inline_processing"] = self.enable_inline_processing
        
        # Retention
        result["mdm_retention_days"] = self.mdm_retention_days
        result["full_message_retention_days"] = self.full_message_retention_days
        result["flagged_or_reported_message_retention_days"] = self.flagged_or_reported_message_retention_days
        
        # Security settings
        if self.abuse_mailboxes:
            result["abuse_mailboxes"] = self.abuse_mailboxes
        result["allow_unauthenticated_user_reports"] = self.allow_unauthenticated_user_reports
        result["require_message_access_justification"] = self.require_message_access_justification
        
        # IP allowlist
        if self.ip_allowlist_json:
            result["ip_allowlist_json"] = [entry.to_dict() for entry in self.ip_allowlist_json]
        
        # Export configs (only include if sensitive data requested)
        if include_sensitive:
            if self.audit_events_export:
                audit_dict = self.audit_events_export.to_dict()
                if audit_dict:
                    result["audit_events_export"] = audit_dict
            
            if self.message_export:
                message_dict = self.message_export.to_dict()
                if message_dict:
                    result["message_export"] = message_dict
        
        # Telemetry
        if self.telemetry:
            result["telemetry"] = self.telemetry.to_dict()
        
        return result