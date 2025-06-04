from . import db
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

class DiscordIntegration(db.Model):
    __tablename__ = 'discord_integrations'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    integration_name = Column(String(100), nullable=False)
    # TODO: Implement actual encryption/decryption for this field
    bot_token_encrypted = Column(Text, nullable=False) # Store encrypted token
    guild_id = Column(String(100), nullable=True) # Discord Server ID
    default_channel_id = Column(String(100), nullable=True) # Default Discord Channel ID
    status = Column(String(50), nullable=False, default='inactive') # e.g., active, inactive, error_token
    last_error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship('User', back_populates='discord_integrations')

    def __repr__(self):
        return f'<DiscordIntegration {self.id} - {self.integration_name} (User {self.user_id})>'

# Add the relationship to the User model if it's not already defined elsewhere for back_populates
# User.discord_integrations = relationship('DiscordIntegration', order_by=DiscordIntegration.id, back_populates='user')
